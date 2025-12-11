from portfolio_source_collector.adapters.binance import BinanceAdapter
from portfolio_source_collector.core.config import BinanceConfig


def test_binance_adapter_parses_balances(monkeypatch) -> None:
    config = BinanceConfig(api_key="key", api_secret="secret")
    adapter = BinanceAdapter(config=config, client=None)

    sample = {
        "balances": [
            {"asset": "USDT", "free": "1.5", "locked": "0.5"},
            {"asset": "BTC", "free": "0", "locked": "0"},
        ]
    }

    monkeypatch.setattr(adapter, "_signed_get", lambda path, params=None: sample)

    balances = adapter.fetch_balances()
    assert len(balances) == 1
    assert balances[0].currency == "USDT"
    assert balances[0].total == 2.0


def test_binance_positions_aggregate_spot_and_earn(monkeypatch) -> None:
    config = BinanceConfig(api_key="key", api_secret="secret")
    adapter = BinanceAdapter(config=config, client=None)

    spot = {
        "balances": [
            {"asset": "USDT", "free": "1", "locked": "1"},
        ]
    }
    earn = {
        "rows": [
            {"asset": "USDT", "totalAmount": "3"},
        ]
    }

    def fake_signed_get(path, params=None):
        if "account" in path:
            return spot
        if "flexible" in path:
            return earn
        return {"rows": []}

    monkeypatch.setattr(adapter, "_signed_get", fake_signed_get)

    positions = adapter.fetch_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "USDT"
    assert positions[0].quantity == 5.0  # 2 spot + 3 earn
