from typing import Annotated

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
    create_db_and_tables,
    get_session,
)
from seed import seed_blockchains_and_tokens

app = FastAPI()


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
                    "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                    "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                }
            ]
        ),
    ],
    session: Session = Depends(get_session),
):
    from_token = session.exec(
        select(TokenAddress)
        .where(TokenAddress.chain_id == quote.fromToken.chain_id)
        .where(TokenAddress.address == quote.fromToken.address)
    ).first()
    if not from_token:
        raise HTTPException(status_code=404, detail="`fromToken` token not found")
    to_token = session.exec(
        select(TokenAddress)
        .where(TokenAddress.chain_id == quote.toToken.chain_id)
        .where(TokenAddress.address == quote.toToken.address)
    ).first()
    if not to_token:
        raise HTTPException(status_code=404, detail="`toToken` token not found")
    fee_token = session.exec(
        select(TokenAddress)
        .where(TokenAddress.chain_id == quote.feeToken.chain_id)
        .where(TokenAddress.address == quote.feeToken.address)
    ).first()
    if not fee_token:
        raise HTTPException(status_code=404, detail="`feeToken` token not found")
    return {"message": "Hello World"}


@app.get("/tokens", response_model=list[TokenPublic])
async def get_tokens(session: Session = Depends(get_session)):
    return session.exec(select(Token)).all()


@app.get("/chains", response_model=list[ChainPublic])
async def get_chains(session: Session = Depends(get_session)):
    return session.exec(select(Chain)).all()
