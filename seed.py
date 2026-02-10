"""
Database seeding for chains, tokens, and token addresses.

This module provides helpers to populate the database with a baseline set of
supported blockchains and tokens, along with their per-chain contract addresses.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Sequence

from sqlalchemy import exc
from sqlmodel import Session

from database import engine
from model.chain import Chain
from model.token import Token, TokenAddress


def _add_all(session: Session, items: Iterable[object]) -> None:
    """
    Add a collection of ORM objects to the session and flush/commit once.

    Args:
        session: Active database session.
        items: ORM objects to add.
    """
    session.add_all(list(items))
    session.commit()


def _seed_chains() -> list[Chain]:
    """
    Build the initial list of chains to seed.

    Returns:
        A list of `Chain` objects (not yet persisted).
    """
    return [
        Chain(id=1, name="Ethereum", slug="eth"),
        Chain(id=8453, name="Base", slug="base"),
        Chain(id=10, name="Optimism", slug="optimism"),
    ]


def _seed_tokens() -> list[Token]:
    """
    Build the initial list of tokens to seed.

    Returns:
        A list of `Token` objects (not yet persisted).
    """
    return [
        Token(name="Circle USD", symbol="USDC", slug="circle-usd", decimals=6),
        Token(name="Wrapped ETH", symbol="WETH", slug="wrapped-ethereum", decimals=18),
    ]


def _seed_token_addresses(
    *,
    chains: Sequence[Chain],
    tokens: Sequence[Token],
) -> list[TokenAddress]:
    """
    Build the initial list of token addresses to seed.

    Args:
        chains: Persisted chains (with ids available).
        tokens: Persisted tokens (with ids available).

    Returns:
        A list of `TokenAddress` objects (not yet persisted).

    Raises:
        KeyError: If an expected chain/token slug is missing from the inputs.
    """
    chain_id = {c.slug: c.id for c in chains}
    token_id = {t.slug: t.id for t in tokens}

    return [
        # WETH
        TokenAddress(
            address="0x4200000000000000000000000000000000000006",
            chain_id=chain_id["optimism"],
            token_id=token_id["wrapped-ethereum"],
        ),
        TokenAddress(
            address="0x4200000000000000000000000000000000000006",
            chain_id=chain_id["base"],
            token_id=token_id["wrapped-ethereum"],
        ),
        # USDC
        TokenAddress(
            address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
            chain_id=chain_id["optimism"],
            token_id=token_id["circle-usd"],
        ),
        TokenAddress(
            address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            chain_id=chain_id["base"],
            token_id=token_id["circle-usd"],
        ),
    ]


def seed_blockchains_and_tokens() -> None:
    """
    Seed the database with baseline chains, tokens, and their contract addresses.

    This performs the inserts in three steps (chains, tokens, token addresses),
    committing once per step.
    """
    try:
        with Session(engine) as session:
            chains = _seed_chains()
            _add_all(session, chains)

            tokens = _seed_tokens()
            _add_all(session, tokens)

            token_addresses = _seed_token_addresses(chains=chains, tokens=tokens)
            _add_all(session, token_addresses)
    except exc.IntegrityError:
        # Data already exists, silently skip
        pass
