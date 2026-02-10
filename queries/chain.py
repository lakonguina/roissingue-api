"""Chain database queries."""

from sqlmodel import Session, select

from model.chain import Chain


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


def get_chains(session: Session) -> list[Chain]:
    """
    Retrieve all chains.

    Args:
        session: Active database session.

    Returns:
        All chains in a list.
    """
    return session.exec(select(Chain)).all()
