import os
from typing import Annotated

import requests
from coingecko_sdk import AsyncCoingecko
from fastapi import Body, Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import exc
from sqlmodel import Session, select

from database import (
    Chain,
    ChainPublic,
    Quote,
    Token,
    TokenAddress,
    TokenPublic,
    TokenQuote,
    TokenQuoteBySlug,
    create_db_and_tables,
    get_session,
)
from seed import seed_blockchains_and_tokens

app = FastAPI()
coingecko_client = AsyncCoingecko(
    demo_api_key=os.environ.get("COINGECKO_DEMO_API_KEY"), environment="demo"
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()
    try:
        seed_blockchains_and_tokens()
    except exc.IntegrityError:
        print("Already seeded")


@app.post("/quote")
async def post_quote(
    quote: Annotated[
        Quote,
        Body(
            examples=[
                {
                    "fromToken": {
                        "chainId": 10,
                        "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                    },
                    "toToken": {
                        "chainId": 8453,
                        "address": "0x4200000000000000000000000000000000000006",
                    },
                    "feeToken": {
                        "chainId": 10,
                        "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                    },
                    "amount": "100000",
                    "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                    "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                }
            ]
        ),
    ],
    session: Session = Depends(get_session),
):
    tokens_to_check = [quote.from_token, quote.fee_token]
    if isinstance(quote.to_token, TokenQuote):
        tokens_to_check.append(quote.to_token)
        for token in tokens_to_check:
            token_in_db = session.exec(
                select(TokenAddress)
                .where(TokenAddress.chain_id == token.chain_id)
                .where(TokenAddress.address == token.address)
            ).first()
            if not token_in_db:
                raise HTTPException(
                    status_code=404,
                    detail=f"Token with address {token.address} and chain id {token.chain_id} not found",
                )
    elif isinstance(quote.to_token, TokenQuoteBySlug):
        to_token_in_db = session.exec(
            select(Token).where(Token.slug == quote.to_token.slug)
        ).first()
        if not to_token_in_db:
            raise HTTPException(
                status_code=404,
                detail=f"Token with slug {quote.to_token.slug} not found",
            )

    for chain_id in quote.allow_chains + quote.deny_chains:
        chain_db = session.exec(select(Chain).where(Chain.slug == chain_id)).first()
        if not chain_db:
            raise HTTPException(
                status_code=404,
                detail=f"Token with address {token.address} and chain id {token.chain_id} not found.",
            )

    """
    # Check for DEXs with the best liquidity
    response = requests.post(
        "https://api.biconomy.io/v1/quote",
        headers={"Content-Type": "application/json"},
        json={
            "mode": "eoa",
            "ownerAddress": quote.from_address,
            "simulate": False,
            "fundingTokens": [
                {
                    "tokenAddress": quote.from_token.address,
                    "chainId": quote.from_token.chain_id,
                    "amount": quote.amount,
                },
            ],
            "feeToken": {
                "address": quote.fee_token.address,
                "chainId": quote.fee_token.chain_id,
            },
            "composeFlows": [
                {
                    "type": "/instructions/intent-simple",
                    "data": {
                        "srcChainId": quote.from_token.chain_id,
                        "dstChainId": quote.to_token.chain_id,
                        "srcToken": quote.from_token.address,
                        "dstToken": quote.to_token.address,
                        "amount": quote.amount,
                        "slippage": quote.slippage,
                    },
                },
                {
                    "type": "/instructions/build",
                    "data": {
                        "functionSignature": "function transfer(address to, uint256 value)",
                        "args": [
                            quote.to_address,
                            {
                                "type": "runtimeErc20Balance",
                                "tokenAddress": quote.to_token.address,
                                "constraints": {"gte": "1"},
                            },
                        ],
                        "to": quote.to_token.address,
                        "chainId": quote.to_token.chain_id,
                    },
                },
            ],
        },
    )
    # TODO: Add output amount in USD
    return response.json()
    """
    return {"message": "test"}


@app.get("/tokens", response_model=list[TokenPublic])
async def get_tokens(session: Session = Depends(get_session)):
    return session.exec(select(Token)).all()


@app.get("/chains", response_model=list[ChainPublic])
async def get_chains(session: Session = Depends(get_session)):
    return session.exec(select(Chain)).all()
