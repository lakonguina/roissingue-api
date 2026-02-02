"""Chain database queries."""

from sqlmodel import Session, select

from database import Chain


def get_chain_by_id(session: Session, chain_id: int) -> Chain | None:
    """
    Retrieve a chain entry by chain id.

    Args:
        session: Active database session.
        chain_id: Blockchain network identifier.

    Returns:
        The matching `Chain` if found, otherwise `None`.
    """
    return session.exec(select(Chain).where(Chain.id == chain_id)).first()
