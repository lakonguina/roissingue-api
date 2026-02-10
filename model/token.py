from sqlalchemy import JSON, BigInteger
from sqlmodel import Field, Relationship, SQLModel

from model.chain import Chain, ChainOut


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
    chain: ChainOut


class TokenPublic(TokenBase):
    addresses: list[TokenAddressPublic]
