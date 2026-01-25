"""Token database queries."""

from sqlmodel import Session, select

from database import Token, TokenAddress


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
