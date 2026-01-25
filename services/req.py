from typing import Any

import httpx


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    r = await client.post(
        url, json=payload, headers=headers, timeout=httpx.Timeout(5.0, read=40.0)
    )
    r.raise_for_status()
    return r.json()
