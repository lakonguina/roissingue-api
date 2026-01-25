"""Quote computation and validation logic."""

from typing import Any

import httpx
from sqlmodel import Session, SQLModel

from database import Token, TokenAddress
from queries.token import get_token_by_address, get_token_by_slug
from services.req import post_json


def filter_chains(
    base_chains: set[int],
    denied_chains: set[int],
    allowed_chains: set[int],
) -> set[int]:
    """Return the set of accepted chains after applying deny/allow filters.

    Denied chains are removed first. If `allowed_chains` is non-empty, the result
    is restricted to the intersection with `allowed_chains`.

    Args:
        base_chains: Base set of candidate chain IDs.
        denied_chains: Chain IDs to exclude.
        allowed_chains: Chain IDs to allow (if non-empty, acts as a whitelist).

    Returns:
        The filtered set of accepted chain IDs.
    """
    accepted = base_chains - denied_chains
    if allowed_chains:
        accepted &= allowed_chains
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


def get_best_output(quotes: dict[str, Any]) -> dict[str, Any]:
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
    return max(quotes, key=lambda q: int(q["returnedData"][0]["minOutputAmount"]))
