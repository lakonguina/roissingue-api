import asyncio
from typing import Annotated

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException
from sqlalchemy import exc
from sqlmodel import Session, select

from database import (
    Chain,
    ChainPublic,
    Quote,
    QuotesBest,
    QuoteWithData,
    Token,
    TokenPublic,
    TokenQuote,
    TokenQuoteBySlug,
    create_db_and_tables,
    get_session,
)
from seed import seed_blockchains_and_tokens
from services.quote_logic import (
    assert_token_address_exists,
    assert_token_slug_exists,
    filter_tokens,
    get_best_output,
    quote_biconomy,
)

BICONOMY_URL = "https://api.biconomy.io/v1/quote"
BICONOMY_HEADERS = {"Content-Type": "application/json"}

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
                    "toToken": {"slug": "circle-usd"},
                    "feeToken": {
                        "chainId": 10,
                        "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                    },
                    "allowChains": [10, 8453],
                    "amount": "100000",
                    "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                    "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                }
            ]
        ),
    ],
    session: Session = Depends(get_session),
):
    # Check if token exists in the database
    if isinstance(quote.to_token, TokenQuote):
        tokens_to_check = [quote.from_token, quote.fee_token]
        tokens_to_check.append(quote.to_token)
        for token in tokens_to_check:
            assert_token_address_exists(session, token.address, token.chain_id)

        async with httpx.AsyncClient() as client:
            quote = await quote_biconomy(
                client,
                quote.from_address,
                quote.to_address,
                quote.from_token.address,
                quote.to_token.address,
                quote.from_token.chain_id,
                quote.to_token.chain_id,
                quote.fee_token.address,
                quote.fee_token.chain_id,
                quote.amount,
                quote.slippage or 0.5,
                BICONOMY_URL,
                BICONOMY_HEADERS,
            )
            if not quote:
                raise HTTPException(
                    status_code=404,
                    detail="No quotes received",
                )
            return quote

    elif isinstance(quote.to_token, TokenQuoteBySlug):
        tokens_accepted = []

        def are_chains_accepted(chains: list[int]) -> None:
            for chain_id in chains:
                chain_db = session.exec(
                    select(Chain).where(Chain.id == chain_id)
                ).first()
                if not chain_db:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Chain with id {chain_id} not found",
                    )

        if quote.allow_chains:
            are_chains_accepted(quote.allow_chains)
        if quote.deny_chains:
            are_chains_accepted(quote.deny_chains)

        to_token_in_db = assert_token_slug_exists(session, quote.to_token.slug)
        tokens_accepted = [tok for tok in to_token_in_db.addresses]

        # Add and remove chains from the quote
        tokens_accepted = filter_tokens(
            tokens_accepted, quote.deny_chains, quote.allow_chains
        )
        if not tokens_accepted:
            raise HTTPException(
                status_code=404,
                detail="No chains accepted",
            )
        # TODO: Implement `allow_swap_providers` and `allow_bridge_providers`

        async with httpx.AsyncClient() as client:
            semaphore = asyncio.Semaphore(2)

            async def safe_quote(tok):
                async with semaphore:
                    try:
                        return QuoteWithData(
                            quote=await quote_biconomy(
                                client,
                                quote.from_address,
                                quote.to_address,
                                quote.from_token.address,
                                tok.address,
                                quote.from_token.chain_id,
                                tok.chain_id,
                                quote.fee_token.address,
                                quote.fee_token.chain_id,
                                quote.amount,
                                quote.slippage or 0.5,
                                BICONOMY_URL,
                                BICONOMY_HEADERS,
                            ),
                            to_token=tok,
                        )
                    except Exception as exc:
                        print(exc)
                        raise HTTPException(
                            status_code=404,
                            detail="Quote failed",
                        )

            fee_token = assert_token_address_exists(
                session, quote.fee_token.address, quote.fee_token.chain_id
            )

            quotes = QuotesBest(
                quotes=await asyncio.gather(
                    *(safe_quote(tok) for tok in tokens_accepted)
                ),
                fee_token=fee_token,
            )
            if not quotes:
                raise HTTPException(
                    status_code=404,
                    detail="No quotes received",
                )
            # TODO: Handle best ouput with fees by converting everthing to usd
            return await get_best_output(quotes)


@app.get("/tokens", response_model=list[TokenPublic])
async def get_tokens(session: Session = Depends(get_session)):
    return session.exec(select(Token)).all()


@app.get("/chains", response_model=list[ChainPublic])
async def get_chains(session: Session = Depends(get_session)):
    return session.exec(select(Chain)).all()
