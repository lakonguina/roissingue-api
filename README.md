# Roissingue API

Unified API for **gasless, multi-chain token swaps** with best-execution routing.

## Goal

Let a dApp request a swap from any token on any supported chain and get back the best route, executed with a single user signature and no native gas token required. Roissingue aggregates quotes, normalises them in USD, picks the best output and relays execution through Biconomy supertransactions.

## Features

- **Quotes** across chains and tokens, with fee estimation and USD conversion (CoinGecko prices, cached)
- **Execution** of signed quotes and status tracking of supertransactions
- **Accounts**: registration, email verification, JWT login, password reset
- **API keys** per user, required on all `/v1` endpoints; executed transactions are persisted per key

| Endpoint | Description |
|---|---|
| `POST /v1/quote` | Best quote for a swap |
| `POST /v1/execute` | Execute a signed quote |
| `GET /v1/status/{supertxHash}` | Execution status |
| `GET /v1/tokens`, `GET /v1/chains` | Supported assets |
| `/register`, `/login`, `/api-keys`, `/transactions` | Account management |

Stack: Python 3.13, FastAPI, SQLModel, httpx, pydantic-settings, Docker. Integration tests in TypeScript with viem (`tests/`).

## Run locally

```bash
cp .env.example .env   # fill in API keys and SMTP settings
uv sync
uv run fastapi dev
```

Interactive docs are available at http://localhost:8000/docs.
