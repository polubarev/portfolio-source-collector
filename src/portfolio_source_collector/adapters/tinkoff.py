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


def _quantity_to_float(quantity: dict) -> float:
    units = float(quantity.get("units", 0))
    nano = float(quantity.get("nano", 0)) / 1_000_000_000
    return units + nano


def _quantity_value(raw: float | str | dict | None) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, dict):
        return _quantity_to_float(raw)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


class TinkoffAdapter(BrokerAdapter):
    def __init__(self, config: TinkoffConfig, client: httpx.Client | None = None) -> None:
        if not config.is_configured():
            raise ValueError("Tinkoff token is not configured")
        self._config = config
        self._client = client or create_http_client(base_url=config.base_url)
        self._instrument_cache: dict[str, str] = {}

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._config.token}"}

    def _post(self, path: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        response = self._client.post(path, json=payload, headers=self._headers())
        response.raise_for_status()
        return response.json()

    def _resolve_symbol(self, security: dict) -> str:
        figi = security.get("figi")
        instrument_type = security.get("instrumentType", "")

        if figi:
            cached = self._instrument_cache.get(figi)
            if cached:
                return cached

            try:
                data = self._post(
                    "/tinkoff.public.invest.api.contract.v1.InstrumentsService/GetInstrumentBy",
                    payload={"idType": "INSTRUMENT_ID_TYPE_FIGI", "id": figi},
                )
                instrument = data.get("instrument", {}) or {}
                ticker = instrument.get("ticker")
                class_code = instrument.get("classCode")
                if ticker:
                    symbol = f"{ticker}.{class_code}" if class_code else ticker
                    self._instrument_cache[figi] = symbol
                    return symbol
                resolved_figi = instrument.get("figi")
                if resolved_figi:
                    self._instrument_cache[figi] = resolved_figi
                    return resolved_figi
            except Exception as exc:  # pragma: no cover - resolution best-effort
                logger.debug("Failed to resolve Tinkoff instrument %s: %s", figi, exc)

        return figi or instrument_type

    def _price_data(self, security: dict) -> dict | None:
        """
        Tinkoff can return different price fields; pick the first present.
        """
        for key in (
            "averagePositionPrice",
            "averagePositionPricePt",
            "averagePositionPriceFifo",
        ):
            value = security.get(key)
            if value:
                return value
        return None

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
        positions: list[Position] = []
        account_ids = self._account_ids()
        if not account_ids:
            logger.info("No Tinkoff accounts found; skipping positions.")
            return positions

        for account_id in account_ids:
            # Use GetPortfolio to get current market pricing for equity calculations
            data = self._post(
                "/tinkoff.public.invest.api.contract.v1.OperationsService/GetPortfolio",
                payload={"accountId": account_id},
            )
            for position in data.get("positions", []):
                qty = _quantity_value(position.get("quantity"))
                if qty == 0:
                    continue

                # GetPortfolio provides 'currentPrice' and 'averagePositionPrice'
                # We prioritize currentPrice for display/valuation if we treat avg_price as "market price" for this tool's purpose,
                # OR we keep avg_price as cost basis.
                # The user issue is "avg_price=0 usd=n/a".
                # If we use currentPrice as avg_price in the model, the CLI will calculate Value = Qty * Price.
                # This effectively shows Market Value, which is what the user likely wants for "Equity".
                current_price = _money_to_float(position.get("currentPrice", {}))
                
                # If current price is 0, fall back to average (cost basis)
                if current_price == 0:
                    current_price = _money_to_float(position.get("averagePositionPrice", {}))

                figi = position.get("figi")
                instrument_type = position.get("instrumentType")
                
                # Resolve symbol
                symbol = figi
                if figi:
                     symbol = self._resolve_symbol({"figi": figi, "instrumentType": instrument_type})
                
                currency = position.get("currentPrice", {}).get("currency", "USD").upper()

                positions.append(
                    Position(
                        broker=Broker.TINKOFF,
                        symbol=symbol or "UNKNOWN",
                        quantity=qty,
                        average_price=current_price, # Using market price to ensure USD valuation works
                        currency=currency,
                    )
                )
        return positions
