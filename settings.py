"""
Application configuration loaded from environment variables.

This settings module defines the runtime configuration for both the API
and the website.  It exposes endpoints for interacting with the
Biconomy API, CoinGecko and defines secrets used for user
authentication, email delivery and session management.  All values can
be overridden via environment variables or a ``.env`` file.
"""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Third‑party API endpoints and API keys
    biconomy_execute: str = "https://api.biconomy.io/v1/execute"
    biconomy_quote: str = "https://api.biconomy.io/v1/quote"
    biconomy_explorer: str = "https://network.biconomy.io/v1/explorer"
    biconomy_api_key: str
    coingecko_api_key: str

    # Secret key used to sign JWT tokens and session cookies
    secret_key: str

    # SMTP configuration for sending emails.  These must be supplied in
    # production to enable email verification and password reset.
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool = False
    email_from: str
    email_from_name: str

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
