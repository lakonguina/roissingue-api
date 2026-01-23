from sqlmodel import Session, select

from database import Token, TokenAddress


def get_token_by_address(
    session: Session, address: str, chain_id: int
) -> TokenAddress | None:
    """Retrieve a token by his address and chain id."""
    return session.exec(
        select(TokenAddress)
        .where(TokenAddress.address == address)
        .where(TokenAddress.chain_id == chain_id)
    ).first()


def get_token_by_slug(
    session: Session,
    slug: str,
) -> Token | None:
    """Retrieve a token by his slug."""
    return session.exec(select(Token).where(Token.slug == slug)).first()
