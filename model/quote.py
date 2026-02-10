from typing import Any

from sqlmodel import Field, SQLModel

from model.token import TokenAddress


class TokenQuote(SQLModel):
    chain_id: int = Field(alias="chainId")
    address: str


class TokenQuoteWithAmount(TokenQuote):
    amount: str


class TokenQuoteBySlug(SQLModel):
    slug: str


class Quote(SQLModel):
    from_token: TokenQuoteWithAmount = Field(alias="fromToken")
    to_token: TokenQuote | TokenQuoteBySlug = Field(alias="toToken")
    fee_token: TokenQuote = Field(alias="feeToken")
    # TODO: Only numerical accepted
    # TODO: Add `eth_pydantic_types.Address` as type for both `from_address` and `to_address`
    from_address: str = Field(alias="fromAddress")
    to_address: str = Field(alias="toAddress")
    slippage: float = Field(default=0.05, ge=0.0, le=1.0)
    mode: str = Field(default="eoa")  # Added mode field with default "eoa"
    allow_chains: set[int] = Field(alias="allowChains", default=set([]))
    deny_chains: set[int] = Field(alias="denyChains", default=set([]))
    allow_swap_providers: set[str] = Field(alias="allowSwapProviders", default=set([]))
    deny_swap_providers: set[str] = Field(alias="denySwapProviders", default=set([]))
    allow_bridge_providers: set[str] = Field(
        alias="allowBridgeProviders", default=set([])
    )
    deny_bridge_providers: set[str] = Field(
        alias="denyBridgeProviders", default=set([])
    )


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
