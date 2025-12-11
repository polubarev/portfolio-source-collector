from __future__ import annotations

from typing import Sequence

import httpx

from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.core.config import TinkoffConfig
from portfolio_source_collector.core.http import create_http_client
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.models import Balance, Broker, Position

logger = configure_logging(logger_name=__name__)


def _money_to_float(amount: dict) -> float:
    units = float(amount.get("units", 0))
    nano = float(amount.get("nano", 0)) / 1_000_000_000
    return units + nano


class TinkoffAdapter(BrokerAdapter):
    def __init__(self, config: TinkoffConfig, client: httpx.Client | None = None) -> None:
        if not config.is_configured():
            raise ValueError("Tinkoff token is not configured")
        self._config = config
        self._client = client or create_http_client(base_url=config.base_url)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.token}"}

    def _post(self, path: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        response = self._client.post(path, json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _account_ids(self) -> list[str]:
        if self._config.account_ids:
            return self._config.account_ids
        if self._config.account_id:
            return [self._config.account_id]

        data = self._post(
            "/tinkoff.public.invest.api.contract.v1.UsersService/GetAccounts",
            payload={},
        )
        accounts = data.get("accounts", [])
        ids: list[str] = []
        for account in accounts:
            if account.get("status") == "ACCOUNT_STATUS_OPEN" and account.get("id"):
                ids.append(account["id"])
        return ids

    def fetch_balances(self) -> Sequence[Balance]:
        balances: list[Balance] = []
        account_ids = self._account_ids()
        if not account_ids:
            logger.info("No Tinkoff accounts found; skipping balances.")
            return balances

        for account_id in account_ids:
            data = self._post(
                "/tinkoff.public.invest.api.contract.v1.OperationsService/GetPositions",
                payload={"accountId": account_id},
            )
            for money in data.get("money", []):
                currency = money.get("currency", "USD").upper()
                total = _money_to_float(money)
                if total == 0:
                    continue
                balances.append(
                    Balance(
                        broker=Broker.TINKOFF,
                        currency=currency,
                        available=total,
                        total=total,
                    )
                )
        return balances

    def fetch_positions(self) -> Sequence[Position]:
        # TODO: implement positions via GetPositions securities and futures blocks.
        logger.info("Tinkoff positions not implemented yet.")
        return []
