"""Quote computation and validation logic."""

import asyncio
from typing import Any

import httpx
from aiocache import cached
from fastapi import HTTPException
from sqlmodel import Session

from database import QuotesBest, Token, TokenAddress
from queries.token import get_token_by_address, get_token_by_slug
from services.req import get, post_json

COINGECKO_URL = "https://api.coingecko.com/api/v3/onchain/networks/eth/tokens/0xdac17f958d2ee523a2206206994597c13d831ec7"


def filter_tokens(
    base_tokens: list[TokenAddress],
    denied_chains: set[int],
    allowed_chains: set[int],
) -> set[int]:
    """Return the set of accepted tokens after applying deny/allow filters.

    Args:
        base_tokens: Base set of tokens.
        denied_chains: Chain IDs to exclude.
        allowed_chains: Chain IDs to allow (if non-empty, acts as a whitelist).

    Returns:
        The filtered set of tokens on chain IDs.
    """
    accepted = [tok for tok in base_tokens if tok.chain_id not in denied_chains]
    if allowed_chains:
        return [tok for tok in accepted if tok.chain_id in allowed_chains]
    return accepted


def assert_token_address_exists(
    session: Session,
    address: str,
    chain_id: int,
) -> TokenAddress:
    """Fetch a token address.

    Args:
        session: Active database session.
        address: Token contract address.
        chain_id: Chain/network identifier.

    Returns:
        The matching `TokenAddress`.

    Raises:
        HTTPException: If the token address is not found for the given chain.
    """
    token = get_token_by_address(session, address, chain_id)
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"Token {address} not found on chain {chain_id}",
        )
    return token


def assert_token_slug_exists(
    session: Session,
    slug: str,
) -> Token:
    """Fetch a token by slug.

    Args:
        session: Active database session.
        slug: Token slug (unique identifier).

    Returns:
        The matching `Token`.

    Raises:
        HTTPException: If no token exists for the provided slug.
    """
    token = get_token_by_slug(session, slug)
    if not token:
        raise HTTPException(
            status_code=404,
            detail=f"Token not found for slug {slug}",
        )
    return token


def build_biconomy_payload(
    from_address: str,
    to_address: str,
    from_token_address: str,
    to_token_address: str,
    from_chain_id: str,
    to_chain_id: str,
    fee_token_address: str,
    fee_chain_id: str,
    slippage: float,
    amount: str,
) -> dict[str, Any]:
    """Build the request payload for Biconomy's quote/compose endpoint.

    Args:
        from_address: Address initiating the quote (owner).
        to_address: Recipient address on destination.
        from_token_address: ERC-20 address on source chain.
        to_token_address: ERC-20 address on destination chain.
        from_chain_id: Source chain ID (as expected by Biconomy).
        to_chain_id: Destination chain ID (as expected by Biconomy).
        fee_token_address: Token address used to pay fees.
        fee_chain_id: Chain ID where the fee token is paid.
        slippage: Allowed slippage (typically fraction or percentage depending on API).
        amount: Input amount (string, usually in base units).

    Returns:
        A dict ready to be JSON-encoded and POSTed to Biconomy.
    """
    return {
        "mode": "eoa",
        "ownerAddress": from_address,
        "simulate": False,
        "fundingTokens": [
            {
                "tokenAddress": from_token_address,
                "chainId": from_chain_id,
                "amount": amount,
            },
        ],
        "feeToken": {
            "address": fee_token_address,
            "chainId": fee_chain_id,
        },
        "composeFlows": [
            {
                "type": "/instructions/intent-simple",
                "data": {
                    "srcChainId": from_chain_id,
                    "dstChainId": to_chain_id,
                    "srcToken": from_token_address,
                    "dstToken": to_token_address,
                    "amount": amount,
                    "slippage": slippage,
                },
            },
            {
                "type": "/instructions/build",
                "data": {
                    "functionSignature": "function transfer(address to, uint256 value)",
                    "args": [
                        to_address,
                        {
                            "type": "runtimeErc20Balance",
                            "tokenAddress": to_token_address,
                            "constraints": {"gte": "1"},
                        },
                    ],
                    "to": to_token_address,
                    "chainId": to_chain_id,
                },
            },
        ],
    }


async def quote_biconomy(
    client: httpx.AsyncClient,
    from_address: str,
    to_address: str,
    from_token_address: str,
    to_token_address: str,
    from_chain_id: int,
    to_chain_id: int,
    fee_token_address: str,
    fee_chain_id: int,
    amount: str,
    slippage: float,
    biconomy_url: str,
    biconomy_headers: dict[str, str],
) -> Any:
    """Request a quote from Biconomy and return the parsed JSON response.

    Args:
        client: An initialized `httpx.AsyncClient`.
        from_address: Address initiating the quote (owner).
        to_address: Recipient address on destination.
        from_token_address: ERC-20 address on source chain.
        to_token_address: ERC-20 address on destination chain.
        from_chain_id: Source chain ID.
        to_chain_id: Destination chain ID.
        fee_token_address: Token address used to pay fees.
        fee_chain_id: Chain ID where the fee token is paid.
        amount: Input amount (string, usually in base units).
        slippage: Allowed slippage.
        biconomy_url: Target Biconomy endpoint URL.
        biconomy_headers: Headers to send to Biconomy (e.g. auth keys).

    Returns:
        The JSON-decoded response from Biconomy.
    """
    payload = build_biconomy_payload(
        from_address=from_address,
        to_address=to_address,
        from_token_address=from_token_address,
        to_token_address=to_token_address,
        from_chain_id=from_chain_id,
        to_chain_id=to_chain_id,
        fee_token_address=fee_token_address,
        fee_chain_id=fee_chain_id,
        amount=amount,
        slippage=slippage,
    )
    return await post_json(client, biconomy_url, payload, biconomy_headers)


async def get_best_output(quotes_best: QuotesBest) -> dict[str, Any]:
    """Select the quote with the highest minimum output amount.

    Args:
        quotes: An iterable of quote objects (despite the annotation, this is
            expected to be something like `list[dict[str, Any]]`).

    Returns:
        The quote object that maximizes the `minOutputAmount`.

    Raises:
        KeyError/IndexError/TypeError/ValueError: If the quote structure is not
            as expected or values cannot be converted to int.
    """
    async with httpx.AsyncClient() as client:
        semaphore = asyncio.Semaphore(2)

        @cached(ttl=60 * 30)
        async def safe_get_token_data(tok):
            async with semaphore:
                coingecko_url = (
                    f"https://api.coingecko.com/api/v3/onchain/networks/"
                    f"{tok.chain.slug}/tokens/{tok.address}"
                )
                headers = {"x-cg-demo-api-key": "CG-hFX9GPn4qa6FzGtqb2eyGgad"}
                return await get(client, coingecko_url, headers)

        token_data: list[str, Any] = await asyncio.gather(
            *(safe_get_token_data(q.to_token) for q in quotes_best.quotes),
        )
        token_data_fee = await safe_get_token_data(quotes_best.fee_token)

        for tok in token_data:
            for quo in quotes_best.quotes:
                if (
                    tok.get("data").get("attributes").get("address").lower()
                    == quo.to_token.address.lower()
                ):
                    feePriceUsdPerUnit = float(
                        token_data_fee.get("data").get("attributes").get("price_usd")
                    )
                    feePriceUsd = (
                        float(quo.quote.get("fee").get("amount"))
                        / 10**quotes_best.fee_token.token.decimals
                    ) * feePriceUsdPerUnit

                    toTokenPriceUsdPerUnit = float(
                        tok.get("data").get("attributes").get("price_usd")
                    )

                    outputAmount = float(
                        quo.quote.get("returnedData")[0].get("outputAmount")
                    )
                    minOutputAmount = float(
                        quo.quote.get("returnedData")[0].get("outputAmount")
                    )

                    toTokenPriceUsd = (
                        outputAmount / 10**quo.to_token.token.decimals
                    ) * toTokenPriceUsdPerUnit
                    minToTokenPriceUsd = (
                        minOutputAmount / 10**quo.to_token.token.decimals
                    ) * toTokenPriceUsdPerUnit

                    quo.quote["fee"]["priceUsd"] = feePriceUsd
                    quo.quote["returnedData"][0]["outputAmountUsd"] = toTokenPriceUsd
                    quo.quote["returnedData"][0][
                        "minOutputAmountUsd"
                    ] = minToTokenPriceUsd

                    continue

        return {"token_data": token_data, "quotes": quotes_best.quotes}
