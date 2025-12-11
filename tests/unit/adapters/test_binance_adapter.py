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
