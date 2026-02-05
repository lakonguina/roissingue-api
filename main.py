import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

import httpx
from fastapi import Body, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from sqlalchemy import exc
from sqlmodel import Session, select

from database import (
    Chain,
    ChainPublic,
    Execute,
    Quote,
    QuotePublic,
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
    assert_chains_supported,
    build_biconomy_payload,
    filter_tokens,
    get_token_addresses_by_slug,
    quote_tokens,
)
from services.req import get, post_json

BICONOMY_URL = "https://api.biconomy.io/v1/quote"
BICONOMY_EXECUTE_URL = "https://api.biconomy.io/v1/execute"
BICONOMY_HEADERS = {"Content-Type": "application/json"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    FastAPICache.init(InMemoryBackend())
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
            openapi_examples={
                "USDC_by_slug": {
                    "summary": "To token by slug",
                    "value": {
                        "fromToken": [
                            {
                                "chainId": 10,
                                "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                                "amount": "100000",
                            }
                        ],
                        "toToken": {"slug": "wrapped-ethereum"},
                        "feeToken": {
                            "chainId": 10,
                            "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                        },
                        "allowChains": [10, 8453],
                        "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                    },
                },
                "USDC_crosschain": {
                    "summary": "To token by chainId/address",
                    "value": {
                        "fromToken": [
                            {
                                "chainId": 10,
                                "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                                "amount": "100000",
                            },
                            {
                                "chainId": 1,
                                "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
                                "amount": "100000",
                            },
                        ],
                        "toToken": {
                            "chainId": 8453,
                            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        },
                        "feeToken": {
                            "chainId": 10,
                            "address": "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                        },
                        "allowChains": [10, 8453],
                        "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                    },
                },
            }
        ),
    ],
    session: Session = Depends(get_session),
):
    # Assert chains are supported by roissingue + biconomy
    chain_ids = [token.chain_id for token in quote.from_token]
    chain_ids.append(quote.fee_token.chain_id)
    if isinstance(quote.to_token, TokenQuote):
        chain_ids.append(quote.to_token.chain_id)
    assert_chains_supported(session, chain_ids)
    match quote.to_token:
        # Output is address + chain_id
        case TokenQuote():
            # Build payload
            payload = build_biconomy_payload(quote, quote.to_token)
            # Getting quote
            return await quote_tokens([payload])
        # Output is a slug
        case TokenQuoteBySlug():
            # Build payloads
            token_addresses = get_token_addresses_by_slug(session, quote.to_token.slug)
            payloads = [
                build_biconomy_payload(quote, to_token) for to_token in token_addresses
            ]
            return await quote_tokens(payloads)


@app.post("/token/{chain_slug}/{token_address}/price/usd")
@cache(expire=60 * 60)
async def get_token_price(
    chain_slug: str,
    token_address: str,
):
    async with httpx.AsyncClient() as client:
        coingecko_url = (
            f"https://api.coingecko.com/api/v3/onchain/networks/"
            f"{chain_slug}/tokens/{token_address}"
        )
        headers = {"x-cg-demo-api-key": "CG-hFX9GPn4qa6FzGtqb2eyGgad"}
        return await get(client, coingecko_url, headers)


@app.post("/execute")
async def execute(data: Execute, session: Session = Depends(get_session)):
    async with httpx.AsyncClient() as client:
        return await post_json(
            client,
            BICONOMY_EXECUTE_URL,
            {**data.quote, "payloadToSign": data.payload_to_sign},
            BICONOMY_HEADERS,
        )


@app.get("/tokens", response_model=list[TokenPublic])
async def get_tokens(session: Session = Depends(get_session)):
    return session.exec(select(Token)).all()


@app.get("/chains", response_model=list[ChainPublic])
async def get_chains(session: Session = Depends(get_session)):
    return session.exec(select(Chain)).all()
