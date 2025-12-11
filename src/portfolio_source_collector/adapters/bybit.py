from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Sequence
from urllib.parse import urlencode

import httpx

from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.core.config import BybitConfig
from portfolio_source_collector.core.http import create_http_client
from portfolio_source_collector.models import Balance, Broker, Position


class BybitAdapter(BrokerAdapter):
    def __init__(self, config: BybitConfig, client: httpx.Client | None = None) -> None:
        if not config.is_configured():
            raise ValueError("Bybit credentials are not configured")
        self._config = config
        self._client = client or create_http_client(base_url=config.base_url)

    def _headers(self, query_string: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        sign_payload = f"{timestamp}{self._config.api_key}{self._config.recv_window}{query_string}"
        signature = hmac.new(
            self._config.api_secret.encode(), sign_payload.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "X-BAPI-API-KEY": self._config.api_key or "",
            "X-BAPI-SIGN": signature,
            "X-BAPI-SIGN-TYPE": "2",
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(self._config.recv_window),
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        query_string = urlencode(params, doseq=True)
        headers = self._headers(query_string=query_string)
        response = self._client.get(path, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    def fetch_balances(self) -> Sequence[Balance]:
        data = self._get("/v5/account/wallet-balance", params={"accountType": "UNIFIED"})
        balances: list[Balance] = []
        result = data.get("result", {})
        for account in result.get("list", []):
            for coin in account.get("coin", []):
                def _to_float(value: Any) -> float:
                    try:
                        return float(value)
                    except (TypeError, ValueError):
                        return 0.0

                total = _to_float(coin.get("walletBalance", 0))
                available = _to_float(coin.get("availableToWithdraw", 0))
                if total == 0:
                    continue
                balances.append(
                    Balance(
                        broker=Broker.BYBIT,
                        currency=coin.get("coin", "USD"),
                        available=available,
                        total=total,
                    )
                )
        return balances

    def fetch_positions(self) -> Sequence[Position]:
        # TODO: implement position retrieval via /v5/position/list.
        return []
