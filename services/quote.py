"""Quote computation and validation logic with CoinGecko price integration."""

import asyncio
import re
from typing import Any

import httpx
from aiocache import cached
from fastapi import HTTPException
from sqlmodel import Session, select

from model.quote import Quote, QuotesBest, QuoteWithData
from model.token import Token, TokenAddress
from queries.chain import get_chain_by_id
from queries.token import get_token_by_address
from services.request import get, post
from settings import settings


def _norm_addr(addr: str) -> str:
    """Normalize an Ethereum address to lowercase."""
    return addr.lower()


@cached(ttl=60 * 30)
async def fetch_coingecko_token_data(
    chain_slug: str,
    token_address: str,
    header: dict[str, str] = settings.coingecko_header,
) -> dict[str, Any]:
    """Fetch token metadata and USD price from CoinGecko Onchain endpoint (cached 30min)."""
    url = f"https://api.coingecko.com/api/v3/onchain/networks/{chain_slug}/tokens/{token_address}"
    async with httpx.AsyncClient() as client:
        return await get(client, url, header)


async def fetch_coingecko_token_data_by_chain_id(
    session: Session, chain_id: int, token_address: str
) -> dict[str, Any]:
    """Fetch CoinGecko token data by chain ID, resolving chain slug from database."""
    if not (chain := get_chain_by_id(session, chain_id)):
        raise HTTPException(
            status_code=404, detail=f"Chain with id {chain_id} not supported"
        )
    return await fetch_coingecko_token_data(chain.slug, token_address)


def _slug_from_coingecko_attrs(attrs: dict[str, Any]) -> str:
    """Generate a slug from CoinGecko attributes, preferring canonical ID."""
    if cg_id := (attrs or {}).get("coingecko_coin_id"):
        return str(cg_id).strip().lower()

    name = str(attrs.get("name") or "token").strip().lower()
    symbol = str(attrs.get("symbol") or "token").strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    symbol = re.sub(r"[^a-z0-9]+", "-", symbol).strip("-")
    return f"{name}-{symbol}".strip("-")


def ensure_token_and_address_from_coingecko(
    session: Session, *, chain_id: int, token_address: str, token_data: dict[str, Any]
) -> TokenAddress:
    """Ensure Token and TokenAddress exist in DB using CoinGecko response."""
    addr = _norm_addr(token_address)
    attrs = token_data.get("data", {}).get("attributes", {}) or {}

    # Check if TokenAddress already exists
    if existing := session.exec(
        select(TokenAddress).where(
            TokenAddress.chain_id == chain_id,
            TokenAddress.address == addr,
        )
    ).first():
        existing.extra_data = attrs
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    # Get or create Token
    slug = _slug_from_coingecko_attrs(attrs)
    if not (token := session.exec(select(Token).where(Token.slug == slug)).first()):
        token = Token(
            name=str(attrs.get("name") or slug),
            symbol=str(attrs.get("symbol") or slug).upper(),
            slug=slug,
            decimals=int(attrs.get("decimals")),
        )
        session.add(token)
        session.commit()
        session.refresh(token)

    # Create TokenAddress
    ta = TokenAddress(
        address=addr,
        chain_id=chain_id,
        token_id=token.id,  # type: ignore[arg-type]
        extra_data=attrs,
    )
    session.add(ta)
    session.commit()
    session.refresh(ta)
    return ta


def assert_chains_supported(session: Session, chain_ids: list[int]) -> None:
    """Validate that all chain IDs are supported, raising HTTPException if not."""
    for chain_id in chain_ids:
        if not get_chain_by_id(session, chain_id):
            raise HTTPException(
                status_code=404, detail=f"Chain with id {chain_id} not supported"
            )


def build_biconomy_payload(quote: Quote, to_token: Any) -> dict[str, Any]:
    """Build the request payload for Biconomy's quote/compose endpoint in EOA mode."""
    # Build funding tokens array
    funding_tokens = [
        {
            "tokenAddress": quote.from_token.address,
            "chainId": quote.from_token.chain_id,
            "amount": quote.from_token.amount,
        }
    ]

    # Add fee token if different from funding token
    if not (
        quote.fee_token.address.lower() == quote.from_token.address.lower()
        and quote.fee_token.chain_id == quote.from_token.chain_id
    ):
        funding_tokens.append(
            {
                "tokenAddress": quote.fee_token.address,
                "chainId": quote.fee_token.chain_id,
            }
        )

    # Convert provider lists to comma-separated strings
    deny_swap = (
        ",".join(quote.deny_swap_providers) if quote.deny_swap_providers else None
    )
    deny_bridge = (
        ",".join(quote.deny_bridge_providers) if quote.deny_bridge_providers else None
    )
    allow_swap = (
        ",".join(quote.allow_swap_providers) if quote.allow_swap_providers else None
    )
    allow_bridge = (
        ",".join(quote.allow_bridge_providers) if quote.allow_bridge_providers else None
    )

    # Build intent data with optional providers
    intent_data = {
        "srcChainId": quote.from_token.chain_id,
        "dstChainId": to_token.chain_id,
        "srcToken": quote.from_token.address,
        "dstToken": to_token.address,
        "amount": quote.from_token.amount,
        "slippage": quote.slippage,
        "routeSelectionMode": "fast-quote",
    }

    if deny_swap:
        intent_data["denySwapProviders"] = deny_swap
    if deny_bridge:
        intent_data["denyBridgeProviders"] = deny_bridge
    if allow_swap:
        intent_data["allowSwapProviders"] = allow_swap
    if allow_bridge:
        intent_data["allowBridgeProviders"] = allow_bridge

    return QuoteWithData(
        quote={
            "mode": quote.mode,
            "ownerAddress": quote.from_address,
            "simulate": False,
            "fundingTokens": funding_tokens,
            "feeToken": {
                "address": quote.fee_token.address,
                "chainId": quote.fee_token.chain_id,
            },
            "composeFlows": [
                {
                    "type": "/instructions/intent-simple",
                    "data": intent_data,
                },
                {
                    "type": "/instructions/build",
                    "data": {
                        "functionSignature": "function transfer(address to, uint256 value)",
                        "args": [
                            quote.to_address,
                            {
                                "type": "runtimeErc20Balance",
                                "tokenAddress": to_token.address,
                                "constraints": {"gte": "1"},
                            },
                        ],
                        "to": to_token.address,
                        "chainId": to_token.chain_id,
                    },
                },
            ],
        },
        to_token=to_token,
    )


async def quote_biconomy(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    url: str = settings.biconomy_quote,
    header: dict[str, str] = settings.biconomy_header,
) -> Any:
    """Request a quote from Biconomy API."""
    return QuoteWithData(
        quote=await post(client, url, payload.quote, header),
        to_token=payload.to_token,
    )


async def quote_token(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    semaphore: asyncio.Semaphore,
    url: str = settings.biconomiy_quote,
    headers: dict[str, str] | None = None,
) -> QuoteWithData:
    """Request a single token quote with concurrency control."""
    headers = headers or settings.biconomy_header
    async with semaphore:
        return await quote_biconomy(client, payload, url, headers)


async def quote_tokens(
    payloads: list[dict[str, Any]],
    concurrency: int = 3,
) -> list[QuoteWithData]:
    """Request multiple token quotes concurrently with rate limiting."""
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        jobs = [quote_token(client, payload, semaphore) for payload in payloads]
        return await asyncio.gather(*jobs)


def filter_tokens(
    base_tokens: list[TokenAddress],
    denied_chains: set[int],
    allowed_chains: set[int],
) -> list[TokenAddress]:
    """Return filtered tokens after applying deny/allow chain filters."""
    accepted = [tok for tok in base_tokens if tok.chain_id not in denied_chains]
    return (
        [tok for tok in accepted if tok.chain_id in allowed_chains]
        if allowed_chains
        else accepted
    )


def get_token_addresses_by_slug(session: Session, slug: str) -> list[TokenAddress]:
    """Get all token addresses for a given token slug across all chains."""
    if not (
        token_addresses := session.exec(
            select(TokenAddress)
            .join(Token, TokenAddress.token_id == Token.id)
            .where(Token.slug == slug)
        ).all()
    ):
        raise HTTPException(status_code=404, detail=f"Tokens not found for slug {slug}")
    return token_addresses


async def get_best_output(session: Session, quotes_best: QuotesBest) -> dict[str, Any]:
    """Select the quote with the highest net USD minimum output (min output minus fee)."""
    # Collect unique (chain_id, address) pairs for all tokens
    token_keys = {
        (int(q.to_token.chain_id), _norm_addr(q.to_token.address))
        for q in quotes_best.quotes
        if getattr(q, "to_token", None)
    }
    token_keys.add(
        (int(quotes_best.fee_token.chain_id), _norm_addr(quotes_best.fee_token.address))
    )

    # Fetch CoinGecko data concurrently for all tokens
    async def _fetch(
        chain_id: int, addr: str
    ) -> tuple[tuple[int, str], dict[str, Any]]:
        data = await fetch_coingecko_token_data_by_chain_id(session, chain_id, addr)
        return (chain_id, _norm_addr(addr)), data

    fetched = await asyncio.gather(*(_fetch(cid, addr) for cid, addr in token_keys))
    data_by_key = dict(fetched)

    # Ensure all tokens exist in DB and build price lookup
    price_usd_by_key = {}
    for (chain_id, addr), td in data_by_key.items():
        attrs = td.get("data", {}).get("attributes", {}) or {}
        ensure_token_and_address_from_coingecko(
            session, chain_id=chain_id, token_address=addr, token_data=td
        )
        try:
            price_usd_by_key[(chain_id, addr)] = float(attrs.get("price_usd"))
        except (TypeError, ValueError):
            price_usd_by_key[(chain_id, addr)] = 0.0

    # Resolve fee token decimals
    fee_key = (
        int(quotes_best.fee_token.chain_id),
        _norm_addr(quotes_best.fee_token.address),
    )
    if not (fee_ta := get_token_by_address(session, fee_key[0], fee_key[1])):
        fee_ta = ensure_token_and_address_from_coingecko(
            session,
            chain_id=fee_key[0],
            token_address=fee_key[1],
            token_data=data_by_key[fee_key],
        )

    fee_decimals = int(fee_ta.token.decimals)
    fee_price_per_unit = price_usd_by_key[fee_key]

    # Compute USD values for each quote
    for quo in quotes_best.quotes:
        to_key = (int(quo.to_token.chain_id), _norm_addr(quo.to_token.address))

        # Get or ensure destination token
        if not (
            to_ta := (
                quo.to_token
                if isinstance(quo.to_token, TokenAddress)
                else get_token_by_address(session, to_key[0], to_key[1])
            )
        ):
            to_ta = ensure_token_and_address_from_coingecko(
                session,
                chain_id=to_key[0],
                token_address=to_key[1],
                token_data=data_by_key[to_key],
            )

        to_decimals = int(to_ta.token.decimals)
        to_price_per_unit = price_usd_by_key.get(to_key, 0.0)

        # Calculate fee in USD
        fee_amount_raw = int(quo.quote.get("fee", {}).get("amount") or 0)
        quo.quote["fee"]["priceUsd"] = (
            fee_amount_raw / (10**fee_decimals)
        ) * fee_price_per_unit

        # Calculate output amounts in USD
        returned0 = (quo.quote.get("returnedData") or [{}])[0] or {}
        output_amount_raw = int(returned0.get("outputAmount") or 0)
        min_output_amount_raw = int(
            returned0.get("minOutputAmount") or returned0.get("outputAmount") or 0
        )

        quo.quote["returnedData"][0]["outputAmountUsd"] = (
            output_amount_raw / (10**to_decimals)
        ) * to_price_per_unit
        quo.quote["returnedData"][0]["minOutputAmountUsd"] = (
            min_output_amount_raw / (10**to_decimals)
        ) * to_price_per_unit

    # Return quote with best net USD output
    return max(
        quotes_best.quotes,
        key=lambda q: float(q.quote["returnedData"][0]["minOutputAmountUsd"])
        - float(q.quote["fee"]["priceUsd"]),
    )
