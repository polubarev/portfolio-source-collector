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


def test_binance_positions_separates_spot_funding_earn(monkeypatch) -> None:
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
    funding = [
        {"asset": "USDT", "free": "5", "locked": "0", "frozen": "0"}
    ]

    def fake_signed_get(path, params=None):
        if "account" in path:
            return spot
        if "simple-earn/flexible/position" in path:
            return earn
        if "simple-earn/locked/position" in path:
            return {"rows": []}
        return {"rows": []}

    def fake_signed_post(path, params=None):
        if "funding" in path:
            return funding
        return {}

    monkeypatch.setattr(adapter, "_signed_get", fake_signed_get)
    monkeypatch.setattr(adapter, "_signed_post", fake_signed_post)

    positions = adapter.fetch_positions()
    
    # We expect 3 positions now: Spot (2), Earn (3), Funding (5)
    assert len(positions) == 3
    
    types = {p.account_type for p in positions}
    assert types == {"spot", "earn", "funding"}
    
    amounts = {p.account_type: p.quantity for p in positions}
    assert amounts["spot"] == 2.0
    assert amounts["earn"] == 3.0
    assert amounts["funding"] == 5.0
