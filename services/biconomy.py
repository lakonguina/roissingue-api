import httpx

from model.execute import ExecuteIn, ExecuteOut
from model.status import StatusOut
from services.request import get, post
from settings import settings


async def get_biconomy_status(
    hash: str,
    url: str = settings.biconomy_explorer,
    header: dict[str, str] = settings.biconomy_header,
) -> StatusOut:
    # TODO: Verify the format of the hash
    url = f"{url}/{hash}"
    async with httpx.AsyncClient() as client:
        try:
            return await get(client, url, header)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail="Unexpected error while getting status",
            )


async def post_biconomy_quote(
    data: ExecuteIn,
    url: settings.biconomy_execute,
    header: settings.biconomy_header,
) -> ExecuteOut:
    async with httpx.AsyncClient() as client:
        return await post(
            client,
            url,
            {**data.quote, "payloadToSign": data.payload_to_sign},
            header,
        )
