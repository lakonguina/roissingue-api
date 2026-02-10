"""SQLModel database engine configuration and session management."""

from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

# Database configuration
DATABASE_FILE = Path("database.db")
DATABASE_URL = f"sqlite:///{DATABASE_FILE}"
CONNECT_ARGS = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=CONNECT_ARGS,
)


def create_db_and_tables() -> None:
    """Create all database tables defined in SQLModel metadata."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session scope."""
    with Session(engine) as session:
        yield session
