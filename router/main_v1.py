from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from sqlmodel import Session

from database import get_session
from model.chain import ChainOut
from model.execute import ExecuteIn, ExecuteOut
from model.quote import Quote, QuotesBest, TokenQuote, TokenQuoteBySlug
from model.status import StatusOut
from model.token import TokenPublic
from queries.chain import get_chains
from queries.token import get_tokens
from services.biconomy import get_biconomy_status, post_biconomy_quote
from services.quote import (
    assert_chains_supported,
    build_biconomy_payload,
    get_best_output,
    get_token_addresses_by_slug,
    quote_tokens,
)
from services.user import get_api_key

router = APIRouter(prefix="/v1")


@router.post("/quote")
async def post_quote(
    quote: Annotated[
        Quote,
        Body(
            openapi_examples={
                "USDC_by_slug": {
                    "summary": "To token by slug",
                    "value": {
                        "fromToken": {
                            "chainId": 8453,
                            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                            "amount": "100000000",
                        },
                        "toToken": {"slug": "circle-usd"},
                        "feeToken": {
                            "chainId": 8453,
                            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        },
                        "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "slippage": 0.01,
                    },
                },
                "USDC_crosschain": {
                    "summary": "To token by chainId/address (cross-chain)",
                    "value": {
                        "fromToken": {
                            "chainId": 8453,
                            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                            "amount": "100000000",
                        },
                        "toToken": {
                            "chainId": 10,
                            "address": "0x94b008aa00579c1307b0ef2c499ad98a8ce58e58",
                        },
                        "feeToken": {
                            "chainId": 8453,
                            "address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                        },
                        "fromAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "toAddress": "0x6eBf2153f931334714984c7F5a8E574207927Cc7",
                        "slippage": 0.01,
                        "denySwapProviders": ["gluex"],
                    },
                },
            }
        ),
    ],
    session: Session = Depends(get_session),
    _=Depends(get_api_key),
):
    # Assert chains are supported by roissingue + biconomy
    chain_ids = [quote.from_token.chain_id, quote.fee_token.chain_id]
    if isinstance(quote.to_token, TokenQuote):
        chain_ids.append(quote.to_token.chain_id)
    assert_chains_supported(session, chain_ids)
    match quote.to_token:
        # Output is address + chain_id
        case TokenQuote():
            # Build payload
            payload = build_biconomy_payload(quote, quote.to_token)
            # Getting quote
            quotes = await quote_tokens([payload])
            best = await get_best_output(
                session, QuotesBest(quotes=quotes, fee_token=quote.fee_token)
            )
            return best.quote
        # Output is a slug
        case TokenQuoteBySlug():
            # Build payloads
            token_addresses = get_token_addresses_by_slug(session, quote.to_token.slug)
            payloads = [
                build_biconomy_payload(quote, to_token) for to_token in token_addresses
            ]
            quotes = await quote_tokens(payloads)
            best = await get_best_output(
                session, QuotesBest(quotes=quotes, fee_token=quote.fee_token)
            )
            return best.quote


@router.post("/execute", response_model=ExecuteOut)
async def post_execute(
    data: Annotated[
        ExecuteIn,
        Body(
            openapi_examples={
                "execute": {
                    "summary": "Execute a swap from a signed quote",
                    "value": {
                        "quote": {},
                        "payloadToSign": {},
                    },
                },
            }
        ),
    ],
    session: Session = Depends(get_session),
    _=Depends(get_api_key),
):
    return await post_biconomy_quote(data)


@router.get("/tokens", response_model=list[TokenPublic])
async def get_token(
    session: Session = Depends(get_session),
    chain_ids: Annotated[set[int] | None, Query()] = None,
    _=Depends(get_api_key),
):
    return get_tokens(session, chain_ids)


@router.get("/chains", response_model=list[ChainOut])
async def get_chain(
    session: Session = Depends(get_session),
    _=Depends(get_api_key),
):
    return get_chains(session)


@router.get("/status/{supertxHash}", response_model=StatusOut | dict[str, Any])
async def get_status(
    supertxHash: str,
    _=Depends(get_api_key),
) -> dict[str, Any]:
    return await get_biconomy_status(supertxHash)
