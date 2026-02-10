from typing import Any

from sqlmodel import Field, SQLModel


class ExecuteIn(SQLModel):
    quote: dict[str, Any] = Field()
    payload_to_sign: list[dict[str, Any]] = Field(alias="payloadToSign")


class ExecuteOut(SQLModel):
    success: bool = Field(
        description="Indicates if the supertransaction execution was successful."
    )
    supertxHash: str | None = Field(
        default=None,
        description="The transaction hash of the executed supertransaction, or null if not available.",
    )
    error: str | None = Field(
        default=None,
        description="Error message if the execution failed, or null if successful.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "supertxHash": "0x9a72f87a93c55d8f88e3f8c2a7b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                    "error": None,
                }
            ]
        }
    }
