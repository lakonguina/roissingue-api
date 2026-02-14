"""FastAPI application entry point with database initialization and seeding."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import create_db_and_tables
from router.auth import auth_router
from router.main_v1 import router
from seed import seed_blockchains_and_tokens

app = FastAPI()

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
    seed_blockchains_and_tokens()


app.include_router(auth_router)
app.include_router(router)
