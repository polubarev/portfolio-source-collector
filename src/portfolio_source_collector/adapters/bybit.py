from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Sequence
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

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

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _wallet_coins(self, account_type: str) -> list[dict[str, Any]]:
        try:
            data = self._get("/v5/account/wallet-balance", params={"accountType": account_type})
        except Exception as exc:  # pragma: no cover - network/permission error
            logger.debug("Bybit wallet balance failed for %s: %s", account_type, exc)
            return []
        result = data.get("result", {})
        coins: list[dict[str, Any]] = []
        for account in result.get("list", []):
            coins.extend(account.get("coin", []))
        return coins

    def _transfer_coins(self, account_type: str) -> list[dict[str, Any]]:
        """
        Funding/Earn balances are accessible via asset transfer API.
        """
        try:
            data = self._get(
                "/v5/asset/transfer/query-account-coin-balance",
                params={"accountType": account_type},
            )
        except Exception as exc:  # pragma: no cover - network/permission error
            logger.debug("Bybit transfer balance failed for %s: %s", account_type, exc)
            return []
        result = data.get("result", {})
        coins = result.get("balance") or result.get("list") or []
        return coins

    def _parse_balance_coin(self, coin: dict[str, Any], account_type: str) -> Balance | None:
        currency = coin.get("coin") or coin.get("currency") or "USD"
        total = self._to_float(
            coin.get("walletBalance")
            or coin.get("transferBalance")
            or coin.get("equity")
            or coin.get("balance")
            or 0
        )
        available = self._to_float(
            coin.get("availableToWithdraw")
            or coin.get("transferBalance")
            or coin.get("walletBalance")
            or coin.get("equity")
            or 0
        )
        if total == 0 and available == 0:
            return None
        return Balance(
            broker=Broker.BYBIT,
            currency=currency,
            available=available,
            total=total,
            account_type=account_type,
        )

    def fetch_balances(self) -> Sequence[Balance]:
        balances: list[Balance] = []
        account_sources = [
            ("unified_trading", "wallet", "UNIFIED"),
            ("funding", "transfer", "FUND"),
            # Earn/Investment products; try wallet INVESTMENT first, then transfer EARN.
            ("earn", "wallet", "INVESTMENT"),
            ("earn", "transfer", "EARN"),
        ]
        for account_label, method, account_type in account_sources:
            coins = (
                self._wallet_coins(account_type)
                if method == "wallet"
                else self._transfer_coins(account_type)
            )
            for coin in coins:
                bal = self._parse_balance_coin(coin, account_label)
                if bal:
                    balances.append(bal)

        return balances

    def _fetch_earn_positions(self) -> list[Position]:
        """
        Fetch Bybit Flexible Savings positions (Earn).
        """
        positions: list[Position] = []
        try:
            # Flexible savings
            data = self._get("/v5/earn/position", params={"category": "FlexibleSaving"})
            result = data.get("result", {})
            rows = result.get("list", [])
            for row in rows:
                 asset = row.get("coin")
                 amount = self._to_float(row.get("amount"))
                 if amount > 0:
                     positions.append(
                         Position(
                             broker=Broker.BYBIT,
                             symbol=asset,
                             quantity=amount,
                             average_price=None,
                             currency=asset,
                             account_type="earn",
                         )
                     )
            logger.info(f"Bybit Earn: Fetched {len(positions)} positions")
        except Exception as exc:
            logger.warning("Bybit earn fetch failed: %s", exc)
        return positions

    def fetch_positions(self) -> Sequence[Position]:
        positions: list[Position] = []
        
        # 1. Unified Trading (Wallet)
        try:
            coins = self._wallet_coins("UNIFIED")
            for coin in coins:
                raw_qty = self._to_float(
                    coin.get("walletBalance") or coin.get("equity")
                )
                if raw_qty == 0:
                    continue
                positions.append(
                    Position(
                        broker=Broker.BYBIT,
                        symbol=coin.get("coin", "USD"),
                        quantity=raw_qty,
                        average_price=None,
                        currency=coin.get("coin", "USD"),
                        account_type="unified_trading",
                    )
                )
        except Exception:
            pass

        # 2. Funding Account (Transfer Balance)
        # Note: Some users report UNIFIED wallet endpoint covers Funding, but API docs say check transfer/query-account-coin-balance 
        # or separate wallet call if not fully unified. We'll try explicit Funding fetch.
        try:
            fund_coins = self._transfer_coins("FUND")
            for coin in fund_coins:
                qty = self._to_float(coin.get("walletBalance") or coin.get("transferBalance") or coin.get("balance"))
                if qty == 0:
                     continue
                positions.append(
                    Position(
                        broker=Broker.BYBIT,
                        symbol=coin.get("coin", "USD"),
                        quantity=qty,
                        average_price=None,
                        currency=coin.get("coin", "USD"),
                        account_type="funding",
                    )
                )
        except Exception:
            pass

        # 3. Earn (Staked Positions)
        positions.extend(self._fetch_earn_positions())

        return positions
