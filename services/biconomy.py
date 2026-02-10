"""Biconomy API client for status checks and quote execution."""

import httpx
from fastapi import HTTPException

from model.execute import ExecuteIn, ExecuteOut
from model.status import StatusOut
from services.request import get, post
from settings import settings


async def get_biconomy_status(
    hash: str,
    url: str | None = None,
    headers: dict[str, str] | None = None,
) -> StatusOut:
    """Retrieve the status of a Biconomy transaction by hash."""
    base_url = url or settings.biconomy_explorer
    request_headers = headers or settings.biconomy_header

    # TODO: Verify the format of the hash
    endpoint = f"{base_url}/{hash}"

    async with httpx.AsyncClient() as client:
        try:
            return await get(client, endpoint, request_headers)
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch status from Biconomy",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error while getting status",
            )


async def post_biconomy_quote(
    data: ExecuteIn,
    url: str | None = None,
    headers: dict[str, str] | None = None,
) -> ExecuteOut:
    """Execute a Biconomy quote with the provided payload."""
    endpoint = url or settings.biconomy_execute
    request_headers = headers or settings.biconomy_header

    payload = {
        **data.quote,
        "payloadToSign": data.payload_to_sign,
    }

    async with httpx.AsyncClient() as client:
        try:
            return await post(client, endpoint, payload, request_headers)
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to execute quote on Biconomy: {str(e)}",
            ) from e
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Unexpected error while executing quote: {str(e)}",
            ) from e
