"""Logic related to quoting"""

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
    """Return the set of accepted chains after applying a deny and allow filters.

    Denied chains are removed. If allowed chains is not empty then accepted chains
    are restricted to it.

    Args:
        base_chains: A set of chains serving as base.
        denied_chains: Denied chains.
        allowed_chains: Chains allowed.

    Returns:
        A new set containing the accepted chains id.
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
    """Assert a token is existing in a database searching by address and chain id."""
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
    """Assert a token is existing in a database searching by slug."""
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
    return max(quotes, key=lambda q: int(q["returnedData"][0]["minOutputAmount"]))
