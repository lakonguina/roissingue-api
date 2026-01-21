from typing import Annotated

from pydantic import confloat
from sqlalchemy import BigInteger
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine, select


class TokenQuote(SQLModel):
    chain_id: int = Field(alias="chainId")
    address: str


class Quote(SQLModel):
    fromToken: TokenQuote = Field()
    toToken: TokenQuote = Field()
    feeToken: TokenQuote = Field()
    from_address: str = Field(alias="fromAddress")
    to_address: str = Field(alias="toAddress")
    slippage: float = Field(default=0.05, ge=0.0, le=1.0)
    allow_chains: list[int] = Field(alias="allowChains", default=[])
    deny_chains: list[int] = Field(alias="denyChains", default=[])


class ChainPublic(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)


class Chain(ChainPublic, table=True):
    __tablename__ = "chains"
    tokens: list["TokenAddress"] = Relationship(back_populates="chain")


class TokenBase(SQLModel):
    name: str = Field(unique=True)
    symbol: str = Field(index=True)


class Token(TokenBase, table=True):
    __tablename__ = "tokens"
    id: int | None = Field(default=None, primary_key=True)
    addresses: list["TokenAddress"] = Relationship(back_populates="token")


class TokenAddressBase(SQLModel):
    address: str = Field()


class TokenAddress(TokenAddressBase, table=True):
    __tablename__ = "token_addresses"
    id: int | None = Field(default=None, primary_key=True)
    token_id: int = Field(foreign_key="tokens.id", index=True)
    chain_id: int = Field(foreign_key="chains.id", index=True, sa_type=BigInteger)
    token: Token = Relationship(back_populates="addresses")
    chain: Chain = Relationship(back_populates="tokens")


class TokenAddressPublic(TokenAddressBase):
    chain: ChainPublic


class TokenPublic(TokenBase):
    addresses: list[TokenAddressPublic]


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
