from typing import Any

from sqlalchemy import JSON, BigInteger
from sqlmodel import Field, Relationship, Session, SQLModel, create_engine


class TokenQuote(SQLModel):
    chain_id: int = Field(alias="chainId")
    address: str


class TokenQuoteWithAmount(TokenQuote):
    amount: str


class TokenQuoteBySlug(SQLModel):
    slug: str


class Quote(SQLModel):
    from_token: list[TokenQuoteWithAmount] = Field(alias="fromToken", default=[])
    to_token: TokenQuote | TokenQuoteBySlug = Field(alias="toToken")
    fee_token: TokenQuote = Field(alias="feeToken")
    # TODO: Only numerical accepted
    # TODO: Add `eth_pydantic_types.Address` as type for both `from_address` and `to_address`
    from_address: str = Field(alias="fromAddress")
    to_address: str = Field(alias="toAddress")
    slippage: float = Field(default=0.05, ge=0.0, le=1.0)
    allow_chains: set[int] = Field(alias="allowChains", default=set([]))
    deny_chains: set[int] = Field(alias="denyChains", default=set([]))
    allow_swap_providers: set[str] = Field(alias="allowSwapProviders", default=set([]))
    deny_swap_providers: set[str] = Field(alias="allowSwapProviders", default=set([]))
    allow_bridge_providers: set[str] = Field(
        alias="allowBridgeProviders", default=set([])
    )
    deny_bridge_providers: set[str] = Field(
        alias="allowBridgeProviders", default=set([])
    )


class ChainPublic(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    slug: str = Field(unique=True, index=True)


class Chain(ChainPublic, table=True):
    __tablename__ = "chains"
    tokens: list["TokenAddress"] = Relationship(back_populates="chain")


class TokenBase(SQLModel):
    name: str = Field(unique=True)
    symbol: str = Field(index=True)
    slug: str = Field(index=True, unique=True)


class Token(TokenBase, table=True):
    __tablename__ = "tokens"
    id: int | None = Field(default=None, primary_key=True)
    addresses: list["TokenAddress"] = Relationship(back_populates="token")
    decimals: int = Field()


class TokenAddressBase(SQLModel):
    address: str = Field()


class TokenAddress(TokenAddressBase, table=True):
    __tablename__ = "token_addresses"
    id: int | None = Field(default=None, primary_key=True)
    extra_data: dict | None = Field(default=None, sa_type=JSON)
    token_id: int = Field(foreign_key="tokens.id", index=True)
    chain_id: int = Field(foreign_key="chains.id", index=True, sa_type=BigInteger)
    token: Token = Relationship(back_populates="addresses")
    chain: Chain = Relationship(back_populates="tokens")


class TokenAddressPublic(TokenAddressBase):
    chain: ChainPublic


class TokenPublic(TokenBase):
    addresses: list[TokenAddressPublic]


class QuoteWithData(SQLModel):
    quote: dict[str, Any]
    to_token: TokenAddress | TokenQuote


class QuotesBest(SQLModel):
    quotes: list[QuoteWithData]
    fee_token: TokenQuote


class QuotePublic(SQLModel):
    quote: dict[str, Any]


class QuoteBestsPublic(SQLModel):
    quotes: list[QuotePublic]


class Execute(SQLModel):
    quote: dict[str, Any] = Field()
    payload_to_sign: list[dict[str, Any]] = Field(alias="payloadToSign")


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, echo=True, connect_args=connect_args)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
