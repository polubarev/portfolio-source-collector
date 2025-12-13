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

    def _signed_post(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        timestamp = int(time.time() * 1000)
        payload = {**params, "timestamp": timestamp}
        query = urlencode(payload, doseq=True)
        signature = hmac.new(
            self._config.api_secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        headers = {"X-MBX-APIKEY": self._config.api_key}
        # For POST, Binance typically expects params in query string or body. 
        # v3/order uses params in query or body. get-funding-asset is SAPI.
        # SAPI docs say "signed" endpoint.
        # usually query string is safest for signature match.
        response = self._client.post(path, params={**payload, "signature": signature}, headers=headers)
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
        positions: list[Position] = []

        # Spot balances
        try:
            data = self._signed_get("/api/v3/account")
            for entry in data.get("balances", []):
                free = float(entry.get("free", 0))
                locked = float(entry.get("locked", 0))
                total = free + locked
                if total == 0:
                    continue
                positions.append(
                    Position(
                        broker=Broker.BINANCE,
                        symbol=entry.get("asset", ""),
                        quantity=total,
                        average_price=None,
                        currency=entry.get("asset", ""),
                        account_type="spot",
                    )
                )
        except Exception:
            pass

        # Funding Wallet balances
        try:
            funding_data = self._signed_post(
                "/sapi/v1/asset/get-funding-asset", params={"needBtcValuation": "false"}
            )
            for entry in funding_data:
                free = float(entry.get("free", 0))
                locked = float(entry.get("locked", 0))
                frozen = float(entry.get("frozen", 0))
                total = free + locked + frozen
                if total == 0:
                    continue
                positions.append(
                    Position(
                        broker=Broker.BINANCE,
                        symbol=entry.get("asset", ""),
                        quantity=total,
                        average_price=None,
                        currency=entry.get("asset", ""),
                        account_type="funding",
                    )
                )
        except Exception as exc:
            # Funding endpoint logic might fail on permissions or connectivity; log but don't crash
            pass

        # Earn positions
        earn_positions = self._fetch_simple_earn_positions()
        # Ensure earn positions have account_type set
        for p in earn_positions:
            p.account_type = "earn"
        positions.extend(earn_positions)

        return positions

    def _fetch_simple_earn_positions(self) -> list[Position]:
        earn_positions: list[Position] = []
        endpoints = [
            "/sapi/v1/simple-earn/flexible/position",
            "/sapi/v1/simple-earn/locked/position",
        ]
        for endpoint in endpoints:
            try:
                data = self._signed_get(endpoint)
            except Exception as exc:  # pragma: no cover - defensive; log and continue
                # Avoid failing whole adapter if earn endpoints are unavailable.
                continue
            for item in data.get("rows", []):
                asset = item.get("asset") or item.get("collateralCoin") or ""
                total = float(item.get("totalAmount", 0) or item.get("amount", 0) or 0)
                if total == 0:
                    continue
                earn_positions.append(
                    Position(
                        broker=Broker.BINANCE,
                        symbol=asset,
                        quantity=total,
                        average_price=None,
                        currency=asset,
                    )
                )
        return earn_positions
