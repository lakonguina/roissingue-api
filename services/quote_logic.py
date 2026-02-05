"""Quote computation and validation logic."""

import asyncio
from typing import Any

import httpx
from aiocache import cached
from fastapi import HTTPException
from sqlmodel import Session, select

from database import Quote, QuotesBest, Token, TokenAddress, TokenQuoteWithAmount
from queries.chain import get_chain_by_id
from queries.token import get_token_by_address, get_token_by_slug
from services.req import get, post_json

COINGECKO_URL = "https://api.coingecko.com/api/v3/onchain/networks/eth/tokens/0xdac17f958d2ee523a2206206994597c13d831ec7"
BICONOMY_URL = "https://api.biconomy.io/v1/quote"
BICONOMY_HEADERS = {"Content-Type": "application/json"}


def assert_chains_supported(session: Session, chain_ids: list[int]) -> None:
    # TODO: Can be more performant using one sql statement
    for chain_id in chain_ids:
        chain = get_chain_by_id(session, chain_id)
        if not chain:
            raise HTTPException(
                status_code=404,
                detail=f"Chain with id {chain_id} not supported",
            )


def build_biconomy_payload(
    quote: Quote,
    to_token: Any,
) -> dict[str, Any]:
    """Build the request payload for Biconomy's quote/compose endpoint.

    Args:
        quote: Quote.

    Returns:
        A dict ready to be JSON-encoded and POSTed to Biconomy.
    """
    return {
        "mode": "smart-account",
        "ownerAddress": quote.from_address,
        "simulate": False,
        "feeToken": {
            "address": quote.fee_token.address,
            "chainId": quote.fee_token.chain_id,
        },
        "composeFlows": [
            {
                "type": "/instructions/intent",
                "data": {
                    "slippage": 0.01,
                    "routeSelectionMode": "fast-quote",
                    "inputPositions": [
                        {
                            "chainToken": {
                                "chainId": ftk.chain_id,
                                "tokenAddress": ftk.address,
                            },
                            "amount": ftk.amount,
                        }
                        for ftk in quote.from_token
                    ],
                    "targetPositions": [
                        {
                            "chainToken": {
                                "chainId": to_token.chain_id,
                                "tokenAddress": to_token.address,
                            },
                            "weight": 1,
                        },
                    ],
                },
            },
            {
                "type": "/instructions/build",
                "data": {
                    "functionSignature": "function transfer(address to, uint256 value)",
                    "args": [
                        quote.to_address,
                        {
                            "type": "runtimeErc20Balance",
                            "tokenAddress": to_token.address,
                            "constraints": {"gte": "1"},
                        },
                    ],
                    "to": to_token.address,
                    "chainId": to_token.chain_id,
                },
            },
        ],
    }


async def quote_biconomy(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    biconomy_url: str = BICONOMY_URL,
    biconomy_headers: dict[str, str] = BICONOMY_HEADERS,
) -> Any:
    return await post_json(client, biconomy_url, payload, biconomy_headers)


async def quote_token(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> "QuoteWithData":
    async with semaphore:
        return await quote_biconomy(client, payload, BICONOMY_URL, BICONOMY_HEADERS)


async def quote_tokens(
    payloads: list[dict[str, Any]],
    concurrency: int = 3,
) -> list["QuoteWithData"]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        jobs = [quote_token(client, payload, semaphore) for payload in payloads]
        return await asyncio.gather(*jobs)


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


def get_token_addresses_by_slug(
    session: Session,
    slug: str,
):
    token_addresses = session.exec(
        select(TokenAddress)
        .join(Token, TokenAddress.token_id == Token.id)
        .where(Token.slug == slug)
    ).all()
    if not token_addresses:
        raise HTTPException(
            status_code=404,
            detail=f"Tokens not found for slug {slug}",
        )
    return token_addresses
