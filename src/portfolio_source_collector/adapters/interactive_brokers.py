from __future__ import annotations

from typing import Sequence

import httpx

from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.core.config import IBKRConfig
from portfolio_source_collector.core.http import create_http_client
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.models import Balance, Broker, Position

logger = configure_logging(logger_name=__name__)


class InteractiveBrokersAdapter(BrokerAdapter):
    """
    Uses the Client Portal Web API (via IB Gateway / Client Portal Gateway).
    Assumes the gateway is already authenticated and reachable at base_url.
    """

    def __init__(self, config: IBKRConfig, client: httpx.Client | None = None) -> None:
        if not config.is_configured():
            raise ValueError("Interactive Brokers credentials are not configured")
        self._config = config
        self._client = client or create_http_client(base_url=config.base_url, verify=config.verify_ssl)

    def _get(self, path: str) -> dict:
        response = self._client.get(path)
        response.raise_for_status()
        return response.json()

    def _account_ids(self) -> list[str]:
        if self._config.account_ids:
            return self._config.account_ids
        if self._config.account_id:
            return [self._config.account_id]

        data = self._get("/v1/api/portfolio/accounts")
        ids: list[str] = []
        for account in data:
            acct_id = account.get("id") or account.get("accountId") or account.get("accountid")
            if acct_id:
                ids.append(acct_id)
        return ids

    def fetch_balances(self) -> Sequence[Balance]:
        balances: list[Balance] = []
        account_ids = self._account_ids()
        if not account_ids:
            logger.info("No Interactive Brokers accounts found; skipping balances.")
            return balances

        for account_id in account_ids:
            ledger = self._get(f"/v1/api/portfolio/{account_id}/ledger")
            for currency, details in ledger.items():
                # ledger entries contain cashbalance and possibly settledcash
                cash = details.get("cashbalance") or details.get("settledcash")
                try:
                    total = float(cash)
                except (TypeError, ValueError):
                    continue
                if total == 0:
                    continue
                balances.append(
                    Balance(
                        broker=Broker.INTERACTIVE_BROKERS,
                        currency=str(currency).upper(),
                        available=total,
                        total=total,
                    )
                )
        return balances

    def fetch_positions(self) -> Sequence[Position]:
        # TODO: implement position retrieval via /positions/ or /portfolio/{accountId}/positions.
        logger.info("Interactive Brokers positions not implemented yet.")
        return []
