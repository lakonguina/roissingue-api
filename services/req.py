"""HTTP client utilities."""

from typing import Any

import httpx
from coingecko_sdk import AsyncCoingecko

coingecko_client = AsyncCoingecko(
    demo_api_key="CG-hFX9GPn4qa6FzGtqb2eyGgad",
    environment="demo",
)


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    """
    Send an HTTP POST request with a JSON payload and return the JSON response.

    Args:
        client: An initialized `httpx.AsyncClient` instance.
        url: The target URL to send the POST request to.
        payload: A JSON-serializable dictionary sent as the request body.
        headers: HTTP headers to include with the request.

    Returns:
        The response body parsed as JSON.

    Raises:
        httpx.HTTPStatusError: If the response status code is 4xx/5xx.
        httpx.RequestError: If the request fails due to a transport/network error.
        ValueError: If the response body is not valid JSON.
    """
    r = await client.post(
        url, json=payload, headers=headers, timeout=httpx.Timeout(5.0, read=40.0)
    )
    r.raise_for_status()
    return r.json()
