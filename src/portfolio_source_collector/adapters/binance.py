from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Sequence
from urllib.parse import urlencode

import httpx

from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.core.config import BinanceConfig
from portfolio_source_collector.core.http import create_http_client
from portfolio_source_collector.models import Balance, Broker, Position


class BinanceAdapter(BrokerAdapter):
    def __init__(self, config: BinanceConfig, client: httpx.Client | None = None) -> None:
        if not config.is_configured():
            raise ValueError("Binance credentials are not configured")
        self._config = config
        self._client = client or create_http_client(base_url=config.base_url)

    def _signed_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        timestamp = int(time.time() * 1000)
        payload = {**params, "timestamp": timestamp}
        query = urlencode(payload, doseq=True)
        signature = hmac.new(
            self._config.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        headers = {"X-MBX-APIKEY": self._config.api_key}
        response = self._client.get(path, params={**payload, "signature": signature}, headers=headers)
        response.raise_for_status()
        return response.json()

    def fetch_balances(self) -> Sequence[Balance]:
        data = self._signed_get("/api/v3/account")
        balances: list[Balance] = []
        for entry in data.get("balances", []):
            free = float(entry.get("free", 0))
            locked = float(entry.get("locked", 0))
            total = free + locked
            if total == 0:
                continue
            balances.append(
                Balance(
                    broker=Broker.BINANCE,
                    currency=entry.get("asset", "USD"),
                    available=free,
                    total=total,
                )
            )
        return balances

    def fetch_positions(self) -> Sequence[Position]:
        # TODO: implement position retrieval (e.g., /api/v3/account includes balances only).
        return []
