from database import (
    Chain,
    ChainPublic,
    Quote,
    Token,
    TokenPublic,
    create_db_and_tables,
    get_session,
)
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy import exc
from sqlmodel import Session, select

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
async def get_quote(quote: Quote):
    return {"message": "Hello World"}


@app.get("/tokens", response_model=list[TokenPublic])
async def get_tokens(session: Session = Depends(get_session)):
    return session.exec(select(Token)).all()


@app.get("/chains", response_model=list[ChainPublic])
async def get_chains(session: Session = Depends(get_session)):
    return session.exec(select(Chain)).all()
