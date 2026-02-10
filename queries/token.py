"""Token database queries."""

from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlmodel import Session, select

from model.token import Token, TokenAddress


def get_token_by_address(
    session: Session, address: str, chain_id: int
) -> TokenAddress | None:
    """
    Retrieve a token address entry by address and chain id.

    Args:
        session: Active database session.
        address: Token contract address.
        chain_id: Blockchain network identifier.

    Returns:
        The matching `TokenAddress` if found, otherwise `None`.
    """
    return session.exec(
        select(TokenAddress)
        .where(TokenAddress.address == address)
        .where(TokenAddress.chain_id == chain_id)
    ).first()


def get_token_by_slug(
    session: Session,
    slug: str,
) -> Token | None:
    """
    Retrieve a token by its slug.

    Args:
        session: Active database session.
        slug: Unique token slug.

    Returns:
        The matching `Token` if found, otherwise `None`.
    """
    return session.exec(select(Token).where(Token.slug == slug)).first()


def get_tokens(
    session: Session,
    chain_ids: set[int] | None,
) -> Token | None:
    """
    Retrieve tokens.

    Args:
        session: Active database session.
        chain_ids: A set of chain ids.

    Returns:
        Returns tokens optionnaly filtered by chain ids.
    """
    statement = select(Token).options(
        selectinload(Token.addresses).selectinload(TokenAddress.chain),
    )
    if chain_ids:
        statement = statement.where(
            # Return tokens that have at least one of them chains
            Token.addresses.any(TokenAddress.chain_id.in_(chain_ids))
        ).options(
            # Only load addresses on those chains
            with_loader_criteria(
                TokenAddress,
                TokenAddress.chain_id.in_(chain_ids),
                include_aliases=True,
            )
        )
    return session.exec(statement).all()
