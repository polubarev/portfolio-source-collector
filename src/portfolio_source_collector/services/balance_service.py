from __future__ import annotations

from typing import Iterable, Sequence

import httpx

from portfolio_source_collector.adapters import (
    BinanceAdapter,
    BrokerAdapter,
    BybitAdapter,
    InteractiveBrokersAdapter,
    TinkoffAdapter,
)
from portfolio_source_collector.core.errors import BrokerError
from portfolio_source_collector.core.config import Settings, get_settings
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.models import Balance

logger = configure_logging(logger_name=__name__)


class BalanceService:
    def __init__(
        self, adapters: Iterable[BrokerAdapter] | None = None, settings: Settings | None = None
    ) -> None:
        self._settings = settings or get_settings()
        self._adapters: Sequence[BrokerAdapter] = (
            list(adapters) if adapters is not None else self._build_adapters()
        )

    def _build_adapters(self) -> Sequence[BrokerAdapter]:
        adapters: list[BrokerAdapter] = []
        if self._settings.tinkoff.is_configured():
            adapters.append(TinkoffAdapter(self._settings.tinkoff))
        else:
            logger.info("Skipping Tinkoff adapter; missing token.")

        if self._settings.bybit.is_configured():
            adapters.append(BybitAdapter(self._settings.bybit))
        else:
            logger.info("Skipping Bybit adapter; missing credentials.")

        if self._settings.binance.is_configured():
            adapters.append(BinanceAdapter(self._settings.binance))
        else:
            logger.info("Skipping Binance adapter; missing credentials.")

        if self._settings.ibkr.is_configured():
            adapters.append(InteractiveBrokersAdapter(self._settings.ibkr))
        else:
            logger.info("Skipping Interactive Brokers adapter; missing credentials.")

        return adapters

    def fetch_all(self) -> list[Balance]:
        balances: list[Balance] = []
        for adapter in self._adapters:
            try:
                balances.extend(adapter.fetch_balances())
            except (BrokerError, httpx.HTTPError) as exc:
                logger.warning("Adapter %s failed: %s", adapter.__class__.__name__, exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Unexpected error in adapter %s: %s", adapter.__class__.__name__, exc)
        return balances
