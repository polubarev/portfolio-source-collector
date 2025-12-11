from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Resolve project root (repo root) relative to this file.
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"


class BinanceConfig(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://api.binance.com"

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)


class BybitConfig(BaseModel):
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: str = "https://api.bybit.com"
    recv_window: int = 5000

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)


class TinkoffConfig(BaseModel):
    token: Optional[str] = None
    base_url: str = "https://invest-public-api.tinkoff.ru/rest"
    account_id: Optional[str] = None
    account_ids: list[str] = Field(default_factory=list)

    def is_configured(self) -> bool:
        return bool(self.token)

    @field_validator("account_ids", mode="before")
    @classmethod
    def parse_account_ids(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        # Accept comma-separated string from env
        return [v.strip() for v in value.split(",") if v.strip()]


class IBKRConfig(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    client_id: Optional[int] = None
    account_id: Optional[str] = None
    account_ids: list[str] = Field(default_factory=list)
    ibapi_path: Optional[str] = None
    verify_ssl: bool = True  # retained for backwards compatibility; unused in socket mode.

    def is_configured(self) -> bool:
        return bool(self.host and self.port is not None and self.client_id is not None)

    @field_validator("account_ids", mode="before")
    @classmethod
    def parse_account_ids(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [v.strip() for v in value.split(",") if v.strip()]


class Settings(BaseModel):
    base_currency: str = "USD"
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    bybit: BybitConfig = Field(default_factory=BybitConfig)
    tinkoff: TinkoffConfig = Field(default_factory=TinkoffConfig)
    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @field_validator("base_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(dotenv_path=ENV_PATH, override=False)

    def _to_int(env_value: str | None) -> int | None:
        if env_value is None:
            return None
        try:
            return int(env_value)
        except ValueError:
            return None

    return Settings(
        base_currency=os.getenv("BASE_CURRENCY", "USD"),
        binance=BinanceConfig(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            base_url=os.getenv("BINANCE_BASE_URL", BinanceConfig().base_url),
        ),
        bybit=BybitConfig(
            api_key=os.getenv("BYBIT_API_KEY"),
            api_secret=os.getenv("BYBIT_API_SECRET"),
            base_url=os.getenv("BYBIT_BASE_URL", BybitConfig().base_url),
            recv_window=int(os.getenv("BYBIT_RECV_WINDOW", BybitConfig().recv_window)),
        ),
        tinkoff=TinkoffConfig(
            token=os.getenv("TINKOFF_TOKEN"),
            base_url=os.getenv("TINKOFF_BASE_URL", TinkoffConfig().base_url),
            account_id=os.getenv("TINKOFF_ACCOUNT_ID"),
            account_ids=os.getenv("TINKOFF_ACCOUNT_IDS"),
        ),
        ibkr=IBKRConfig(
            host=os.getenv("IBKR_HOST"),
            port=_to_int(os.getenv("IBKR_PORT")),
            client_id=_to_int(os.getenv("IBKR_CLIENT_ID")),
            account_id=os.getenv("IBKR_ACCOUNT_ID"),
            account_ids=os.getenv("IBKR_ACCOUNT_IDS"),
            ibapi_path=os.getenv("IBKR_API_PATH"),
            verify_ssl=os.getenv("IBKR_VERIFY_SSL", "true").lower() not in {"0", "false", "no"},
        ),
    )
