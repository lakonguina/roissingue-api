"""Logic related to quoting"""

from sqlmodel import Session, SQLModel

from database import Token, TokenAddress
from queries.token import get_token_by_address, get_token_by_slug


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
