import pytest

from portfolio_source_collector.adapters.interactive_brokers import InteractiveBrokersAdapter, _IBAccountClient
from portfolio_source_collector.core.config import IBKRConfig


def test_ibkr_adapter_skips_if_not_configured() -> None:
    config = IBKRConfig()
    with pytest.raises(ValueError):
        InteractiveBrokersAdapter(config=config)


def test_ibkr_adapter_builds_balances(monkeypatch) -> None:
    config = IBKRConfig(host="127.0.0.1", port=7497, client_id=1)

    class FakeIBClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def fetch(self, timeout: float = 5.0):
            balances = [
                {"account": "acct1", "currency": "USD", "amount": 12.5},
                {"account": "acct1", "currency": "EUR", "amount": 0.0},
            ]
            positions: list[dict] = []
            return balances, positions

    monkeypatch.setattr("portfolio_source_collector.adapters.interactive_brokers._IBAccountClient", FakeIBClient)

    adapter = InteractiveBrokersAdapter(config=config)
    balances = adapter.fetch_balances()
    assert len(balances) == 1
    assert balances[0].currency == "USD"
    assert balances[0].total == 12.5


def test_ibkr_adapter_builds_positions(monkeypatch) -> None:
    config = IBKRConfig(host="127.0.0.1", port=7497, client_id=1)

    class FakeIBClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def fetch(self, timeout: float = 5.0):
            balances: list[dict] = []
            positions = [
                {"account": "acct1", "symbol": "AAPL", "currency": "USD", "qty": 10, "avg_cost": 150},
            ]
            return balances, positions

    monkeypatch.setattr("portfolio_source_collector.adapters.interactive_brokers._IBAccountClient", FakeIBClient)

    adapter = InteractiveBrokersAdapter(config=config)
    positions = adapter.fetch_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == 10
