"""This file contains the settings of the application and is used to store
configuration values and environment variables and other important things."""

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    biconomy_execute: str = "https://api.biconomy.io/v1/execute"
    biconomy_quote: str = "https://api.biconomy.io/v1/quote"
    biconomy_explorer: str = "https://network.biconomy.io/v1/explorer"
    biconomy_api_key: str
    coingecko_api_key: str

    @property
    def biconomy_header(self) -> dict[str, str]:
        """Return standard headers for Biconomy API requests."""
        return {
            "Content-Type": "application/json",
            "X-API-KEY": self.biconomy_api_key,
        }

    @property
    def coingecko_header(self) -> dict[str, str]:
        """Return standard headers for Coingecko API requests."""
        return {
            "x-cg-demo-api-key": self.coingecko_api_key,
        }

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
