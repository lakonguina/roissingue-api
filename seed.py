from sqlmodel import Session

from database import Chain, Token, TokenAddress, engine


def seed_blockchains_and_tokens():
    with Session(engine) as session:
        ethereum = Chain(id=1, name="Ethereum")
        base = Chain(id=8453, name="Base")
        optimism = Chain(id=10, name="Optimism")
        blockchains = [ethereum, base, optimism]
        for bln in blockchains:
            session.add(bln)
            session.commit()
            session.refresh(bln)
        usdc = Token(name="Circle USD", symbol="USDC")
        weth = Token(name="Wrapped ETH", symbol="WETH")
        tokens = [usdc, weth]
        for tkn in tokens:
            session.add(tkn)
            session.commit()
            session.refresh(tkn)
        token_addresses = [
            TokenAddress(
                address="0x4200000000000000000000000000000000000006",
                chain_id=optimism.id,
                token_id=weth.id,
            ),
            TokenAddress(
                address="0x4200000000000000000000000000000000000006",
                chain_id=base.id,
                token_id=weth.id,
            ),
            TokenAddress(
                address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
                chain_id=optimism.id,
                token_id=usdc.id,
            ),
            TokenAddress(
                address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                chain_id=base.id,
                token_id=usdc.id,
            ),
        ]
        for tka in token_addresses:
            session.add(tka)
        session.commit()
