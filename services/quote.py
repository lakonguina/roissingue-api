"""Quote computation and validation logic."""

import asyncio
import re
from typing import Any

import httpx
from aiocache import cached
from fastapi import HTTPException
from sqlmodel import Session, select

from model.quote import Quote, QuotesBest, QuoteWithData, TokenQuoteWithAmount
from model.token import Token, TokenAddress
from queries.chain import get_chain_by_id
from queries.token import get_token_by_address, get_token_by_slug
from services.request import get, post
from settings import settings

BICONOMY_URL = "https://api.biconomy.io/v1/quote"
BICONOMY_HEADERS = {"Content-Type": "application/json"}


def _norm_addr(addr: str) -> str:
    return addr.lower()


@cached(ttl=60 * 30)
async def fetch_coingecko_token_data(
    chain_slug: str,
    token_address: str,
    header: dict[str, str] = settings.coingecko_header,
) -> dict[str, Any]:
    """Fetch token metadata + USD price from CoinGecko Onchain endpoint.

    This function is intentionally cached at module level so it can be reused
    by both `get_best_output` and the `/token/{chain_slug}/{token_address}/price/usd` endpoint.
    """
    coingecko_url = (
        f"https://api.coingecko.com/api/v3/onchain/networks/"
        f"{chain_slug}/tokens/{token_address}"
    )
    async with httpx.AsyncClient() as client:
        return await get(client, coingecko_url, header)


async def fetch_coingecko_token_data_by_chain_id(
    session: Session, chain_id: int, token_address: str
) -> dict[str, Any]:
    chain = get_chain_by_id(session, chain_id)
    if not chain:
        raise HTTPException(
            status_code=404, detail=f"Chain with id {chain_id} not supported"
        )
    return await fetch_coingecko_token_data(chain.slug, token_address)


def _slug_from_coingecko_attrs(attrs: dict[str, Any]) -> str:
    # Prefer CoinGecko's canonical id if present; else fallback to name/symbol.
    cg_id = (attrs or {}).get("coingecko_coin_id")
    if cg_id:
        return str(cg_id).strip().lower()
    name = str((attrs or {}).get("name") or "token").strip().lower()
    symbol = str((attrs or {}).get("symbol") or "token").strip().lower()
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    symbol = re.sub(r"[^a-z0-9]+", "-", symbol).strip("-")
    return f"{name}-{symbol}".strip("-")


def ensure_token_and_address_from_coingecko(
    session: Session, *, chain_id: int, token_address: str, token_data: dict[str, Any]
) -> TokenAddress:
    """Ensure Token + TokenAddress exist in DB using CoinGecko response.

    Stores the CoinGecko attributes blob in TokenAddress.extra_data.
    """
    addr = _norm_addr(token_address)
    existing = session.exec(
        select(TokenAddress).where(
            TokenAddress.chain_id == chain_id, TokenAddress.address == addr
        )
    ).first()
    attrs = (token_data or {}).get("data", {}).get("attributes", {}) or {}

    if existing:
        # Keep DB in sync with fresh CoinGecko attributes (price, image, ids, etc.)
        existing.extra_data = attrs
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    slug = _slug_from_coingecko_attrs(attrs)
    token = session.exec(select(Token).where(Token.slug == slug)).first()
    if not token:
        token = Token(
            name=str(attrs.get("name") or slug),
            symbol=str(attrs.get("symbol") or slug).upper(),
            slug=slug,
            decimals=int(attrs.get("decimals")),
        )
        session.add(token)
        session.commit()
        session.refresh(token)

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
    # TODO: Can be more performant using one sql statement
    for chain_id in chain_ids:
        chain = get_chain_by_id(session, chain_id)
        if not chain:
            raise HTTPException(
                status_code=404,
                detail=f"Chain with id {chain_id} not supported",
            )


def build_biconomy_payload(
    quote: Quote,
    to_token: Any,
) -> dict[str, Any]:
    """Build the request payload for Biconomy's quote/compose endpoint in EOA mode.

    Args:
        quote: Quote object containing from_token (single token), to_token, fee_token, etc.
        to_token: The destination token (TokenAddress or TokenQuote).

    Returns:
        A dict ready to be JSON-encoded and POSTed to Biconomy.
    """
    # Build fundingTokens array with from_token and fee_token
    funding_tokens = [
        {
            "tokenAddress": quote.from_token.address,
            "chainId": quote.from_token.chain_id,
            "amount": quote.from_token.amount,
        }
    ]

    # Add fee_token to funding tokens if it's different from from_token
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

    # Convert deny/allow lists to comma-separated strings
    deny_swap_providers = (
        ",".join(quote.deny_swap_providers) if quote.deny_swap_providers else None
    )
    deny_bridge_providers = (
        ",".join(quote.deny_bridge_providers) if quote.deny_bridge_providers else None
    )
    allow_swap_providers = (
        ",".join(quote.allow_swap_providers) if quote.allow_swap_providers else None
    )
    allow_bridge_providers = (
        ",".join(quote.allow_bridge_providers) if quote.allow_bridge_providers else None
    )

    # Build intent-simple data
    intent_data = {
        "srcChainId": quote.from_token.chain_id,
        "dstChainId": to_token.chain_id,
        "srcToken": quote.from_token.address,
        "dstToken": to_token.address,
        "amount": quote.from_token.amount,
        "slippage": quote.slippage,
        "routeSelectionMode": "fast-quote",
    }

    # Add optional deny/allow providers
    if deny_swap_providers:
        intent_data["denySwapProviders"] = deny_swap_providers
    if deny_bridge_providers:
        intent_data["denyBridgeProviders"] = deny_bridge_providers
    if allow_swap_providers:
        intent_data["allowSwapProviders"] = allow_swap_providers
    if allow_bridge_providers:
        intent_data["allowBridgeProviders"] = allow_bridge_providers

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
    return QuoteWithData(
        quote=await post(client, url, payload.quote, header),
        to_token=payload.to_token,
    )


async def quote_token(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    semaphore: asyncio.Semaphore,
) -> "QuoteWithData":
    async with semaphore:
        return await quote_biconomy(client, payload, BICONOMY_URL, BICONOMY_HEADERS)


async def quote_tokens(
    payloads: list[dict[str, Any]],
    concurrency: int = 3,
) -> list["QuoteWithData"]:
    semaphore = asyncio.Semaphore(concurrency)
    async with httpx.AsyncClient() as client:
        jobs = [quote_token(client, payload, semaphore) for payload in payloads]
        return await asyncio.gather(*jobs)


def filter_tokens(
    base_tokens: list[TokenAddress],
    denied_chains: set[int],
    allowed_chains: set[int],
) -> set[int]:
    """Return the set of accepted tokens after applying deny/allow filters.

    Args:
        base_tokens: Base set of tokens.
        denied_chains: Chain IDs to exclude.
        allowed_chains: Chain IDs to allow (if non-empty, acts as a whitelist).

    Returns:
        The filtered set of tokens on chain IDs.
    """
    accepted = [tok for tok in base_tokens if tok.chain_id not in denied_chains]
    if allowed_chains:
        return [tok for tok in accepted if tok.chain_id in allowed_chains]
    return accepted


def get_token_addresses_by_slug(
    session: Session,
    slug: str,
):
    token_addresses = session.exec(
        select(TokenAddress)
        .join(Token, TokenAddress.token_id == Token.id)
        .where(Token.slug == slug)
    ).all()
    if not token_addresses:
        raise HTTPException(
            status_code=404,
            detail=f"Tokens not found for slug {slug}",
        )
    return token_addresses


async def get_best_output(session: Session, quotes_best: QuotesBest) -> dict[str, Any]:
    """Select the quote with the highest *net* USD minimum output (min output minus fee).

    This function:
    - Fetches CoinGecko onchain data for *all* tokens involved (fee token + every to token),
      using the shared cached helper `fetch_coingecko_token_data`.
    - Ensures missing tokens are stored in DB via Token + TokenAddress.
    - Computes USD values for each quote and selects the best one.
    """
    # 1) Build the unique set of (chain_id, address) we need prices for.
    token_keys: set[tuple[int, str]] = set()
    for q in quotes_best.quotes:
        if not getattr(q, "to_token", None):
            continue
        token_keys.add((int(q.to_token.chain_id), _norm_addr(q.to_token.address)))

    token_keys.add(
        (int(quotes_best.fee_token.chain_id), _norm_addr(quotes_best.fee_token.address))
    )

    # 2) Fetch CoinGecko data (cached) for all tokens, concurrently.
    async def _fetch(
        chain_id: int, addr: str
    ) -> tuple[tuple[int, str], dict[str, Any]]:
        data = await fetch_coingecko_token_data_by_chain_id(session, chain_id, addr)
        return (chain_id, _norm_addr(addr)), data

    fetched = await asyncio.gather(*(_fetch(cid, addr) for (cid, addr) in token_keys))
    data_by_key: dict[tuple[int, str], dict[str, Any]] = {k: v for k, v in fetched}

    # 3) Ensure tokens exist in DB and build price lookup.
    price_usd_by_key: dict[tuple[int, str], float] = {}
    for (chain_id, addr), td in data_by_key.items():
        attrs = (td or {}).get("data", {}).get("attributes", {}) or {}
        # Persist if missing (and refresh extra_data even if it exists)
        ensure_token_and_address_from_coingecko(
            session, chain_id=chain_id, token_address=addr, token_data=td
        )
        try:
            price_usd_by_key[(chain_id, addr)] = float(attrs.get("price_usd"))
        except (TypeError, ValueError):
            # If CoinGecko doesn't have price data, treat as 0 (quote will naturally lose).
            price_usd_by_key[(chain_id, addr)] = 0.0

    # 4) Resolve fee token decimals from DB (fee_token in request doesn't carry decimals).
    fee_ta = get_token_by_address(
        session,
        int(quotes_best.fee_token.chain_id),
        _norm_addr(quotes_best.fee_token.address),
    )
    if not fee_ta:
        fee_ta = ensure_token_and_address_from_coingecko(
            session,
            chain_id=int(quotes_best.fee_token.chain_id),
            token_address=_norm_addr(quotes_best.fee_token.address),
            token_data=data_by_key[
                (
                    int(quotes_best.fee_token.chain_id),
                    _norm_addr(quotes_best.fee_token.address),
                )
            ],
        )

    fee_decimals = int(fee_ta.token.decimals)
    fee_price_per_unit = price_usd_by_key[
        (int(quotes_best.fee_token.chain_id), _norm_addr(quotes_best.fee_token.address))
    ]

    # 5) Compute USD values per quote.
    for quo in quotes_best.quotes:
        to_chain_id = int(quo.to_token.chain_id)
        to_addr = _norm_addr(quo.to_token.address)

        to_ta = quo.to_token if isinstance(quo.to_token, TokenAddress) else None
        if not to_ta:
            to_ta = get_token_by_address(session, to_chain_id, to_addr)
        if not to_ta:
            to_ta = ensure_token_and_address_from_coingecko(
                session,
                chain_id=to_chain_id,
                token_address=to_addr,
                token_data=data_by_key[(to_chain_id, to_addr)],
            )

        to_decimals = int(to_ta.token.decimals)
        to_price_per_unit = price_usd_by_key.get((to_chain_id, to_addr), 0.0)
        fee_amount_raw = int(quo.quote.get("fee", {}).get("amount") or 0)
        fee_usd = (fee_amount_raw / (10**fee_decimals)) * fee_price_per_unit
        quo.quote["fee"]["priceUsd"] = fee_usd

        returned0 = (quo.quote.get("returnedData") or [{}])[0] or {}

        output_amount_raw = int(returned0.get("outputAmount") or 0)
        min_output_amount_raw = int(
            returned0.get("minOutputAmount") or returned0.get("outputAmount") or 0
        )

        output_usd = (output_amount_raw / (10**to_decimals)) * to_price_per_unit
        min_output_usd = (min_output_amount_raw / (10**to_decimals)) * to_price_per_unit

        quo.quote["returnedData"][0]["outputAmountUsd"] = output_usd
        quo.quote["returnedData"][0]["minOutputAmountUsd"] = min_output_usd

    # 6) Pick the best net USD output.
    return max(
        quotes_best.quotes,
        key=lambda q: float(q.quote["returnedData"][0]["minOutputAmountUsd"])
        - float(q.quote["fee"]["priceUsd"]),
    )
