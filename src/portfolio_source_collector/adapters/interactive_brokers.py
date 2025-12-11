from __future__ import annotations

import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Any, Sequence

from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.core.config import IBKRConfig, ROOT_DIR
from portfolio_source_collector.core.errors import BrokerError
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.models import Balance, Broker, Position

logger = configure_logging(logger_name=__name__)


class _IBAccountClient:
    """
    Minimal IB API client to fetch cash balances and positions via socket API.
    Uses account summary tags and position callbacks similar to sandbox.py.
    """

    def __init__(self, host: str, port: int, client_id: int, account_filter: list[str] | None = None):
        self._ensure_ibapi_imported()
        self.ibapi_client = importlib.import_module("ibapi.client")
        self.ibapi_wrapper = importlib.import_module("ibapi.wrapper")
        self.ibapi_contract = importlib.import_module("ibapi.contract")

        EWrapper = self.ibapi_wrapper.EWrapper
        EClient = self.ibapi_client.EClient

        class _Client(EWrapper, EClient):
            def __init__(self, outer: "_IBAccountClient") -> None:
                EClient.__init__(self, self)
                self.outer = outer

            def error(
                self,
                reqId: int,
                errorCode: int,
                errorString: str,
                advancedOrderRejectJson: str = "",
                errorTime: str | None = None,
            ) -> None:
                benign = {2104, 2106, 2158}
                if int(errorString) not in benign:
                    outer_msg = f"IB error {errorCode}: {errorString}"
                    logger.warning(outer_msg)
                    if self.outer.error is None:
                        self.outer.error = outer_msg

            def nextValidId(self, orderId: int) -> None:
                # Trigger summary and positions once connected.
                self.reqAccountSummary(1, "All", "NetLiquidation,TotalCashValue,CashBalance")
                self.reqPositions()

            def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:
                tag_lower = tag.lower()
                if tag_lower in {"totalcashvalue", "cashbalance"}:
                    try:
                        amount = float(value)
                    except ValueError:
                        amount = 0.0
                    if account_filter and not _IBAccountClient._account_matches(account, account_filter):
                        return
                    self.outer.balances.append(
                        {
                            "account": account,
                            "currency": currency.upper(),
                            "amount": amount,
                        }
                    )
                elif tag_lower == "netliquidation":
                    try:
                        amount = float(value)
                    except ValueError:
                        amount = 0.0
                    self.outer.net_liquidations.append(
                        {"account": account, "currency": currency.upper(), "amount": amount}
                    )

            def accountSummaryEnd(self, reqId: int) -> None:
                self.outer.summary_done.set()

            def position(self, account: str, contract: Any, pos: float, avgCost: float) -> None:
                if account_filter and not _IBAccountClient._account_matches(account, account_filter):
                    return
                self.outer.positions.append(
                    {
                        "account": account,
                        "symbol": contract.symbol,
                        "sec_type": contract.secType,
                        "currency": contract.currency,
                        "qty": pos,
                        "avg_cost": avgCost,
                    }
                )

            def positionEnd(self) -> None:
                self.outer.positions_done.set()

        self._client_impl = _Client(self)
        self.host = host
        self.port = port
        self.client_id = client_id
        self.summary_done = threading.Event()
        self.positions_done = threading.Event()
        self.balances: list[dict[str, Any]] = []
        self.net_liquidations: list[dict[str, Any]] = []
        self.positions: list[dict[str, Any]] = []
        self.error: str | None = None
        self._account_filter = account_filter

    def fetch(self, timeout: float = 15.0) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        self._client_impl.connect(self.host, self.port, self.client_id)
        thread = threading.Thread(target=self._client_impl.run, daemon=True)
        thread.start()

        # Wait for both summary and positions
        start = time.time()
        while time.time() - start < timeout:
            if self.summary_done.is_set() and self.positions_done.is_set():
                break
            time.sleep(0.1)

        self._client_impl.disconnect()
        thread.join(timeout=1.0)

        if self.error:
            raise BrokerError(self.error)
        return self.balances, self.positions

    @staticmethod
    def _ensure_ibapi_imported() -> None:
        """
        Attempt to import ibapi; if missing, optionally extend sys.path from common locations.
        """
        try:
            importlib.import_module("ibapi.client")
            return
        except ImportError:
            pass

        # Look for extracted TWS API pythonclient relative to repo root.
        candidate = ROOT_DIR / "twsapi_macunix.1037.02" / "IBJts" / "source" / "pythonclient"
        if candidate.exists():
            sys.path.insert(0, str(candidate))
            try:
                importlib.import_module("ibapi.client")
                return
            except ImportError:
                pass

        raise BrokerError("ibapi is not installed. Install it from the IB API package (pythonclient).")

    @staticmethod
    def _account_matches(account: str, filters: list[str]) -> bool:
        for f in filters:
            if not f:
                continue
            if account == f:
                return True
            # Allow matching without the leading 'U' if provided as numeric only.
            if f and account.endswith(f):
                return True
        return False


class InteractiveBrokersAdapter(BrokerAdapter):
    """
    Uses the IB socket API (TWS/IB Gateway) to fetch cash balances.
    """

    def __init__(self, config: IBKRConfig) -> None:
        if not config.is_configured():
            raise ValueError("Interactive Brokers is not configured (host/port/client_id required)")
        self._config = config
        if config.ibapi_path:
            sys.path.insert(0, config.ibapi_path)

    def fetch_balances(self) -> Sequence[Balance]:
        account_filter = (
            self._config.account_ids
            if self._config.account_ids
            else ([self._config.account_id] if self._config.account_id else None)
        )

        default_port = 7496  # Align with TWS default; override via IBKR_PORT
        client = _IBAccountClient(
            host=self._config.host or "127.0.0.1",
            port=self._config.port or default_port,
            client_id=int(self._config.client_id or 1),
            account_filter=account_filter,
        )
        balances_raw, _ = client.fetch()
        balances: list[Balance] = []
        for entry in balances_raw:
            amount = float(entry.get("amount", 0))
            if amount == 0:
                continue
            balances.append(
                Balance(
                    broker=Broker.INTERACTIVE_BROKERS,
                    currency=entry.get("currency", "USD"),
                    available=amount,
                    total=amount,
                )
            )
        return balances

    def fetch_positions(self) -> Sequence[Position]:
        account_filter = (
            self._config.account_ids
            if self._config.account_ids
            else ([self._config.account_id] if self._config.account_id else None)
        )
        default_port = 7496
        client = _IBAccountClient(
            host=self._config.host or "127.0.0.1",
            port=self._config.port or default_port,
            client_id=int(self._config.client_id or 1),
            account_filter=account_filter,
        )
        _, positions_raw = client.fetch()
        positions: list[Position] = []
        for entry in positions_raw:
            positions.append(
                Position(
                    broker=Broker.INTERACTIVE_BROKERS,
                    symbol=str(entry.get("symbol", "")),
                    quantity=float(entry.get("qty", 0) or 0),
                    average_price=float(entry.get("avg_cost", 0) or 0),
                    currency=str(entry.get("currency", "USD")),
                )
            )
        return positions
