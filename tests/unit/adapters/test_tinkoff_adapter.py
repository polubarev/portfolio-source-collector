from portfolio_source_collector.adapters.tinkoff import TinkoffAdapter
from portfolio_source_collector.core.config import TinkoffConfig


def test_tinkoff_adapter_parses_money_balances(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {"accounts": [{"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"}]}
        if "GetPositions" in path:
            # Used for balances
            return {
                "money": [
                    {"currency": "RUB", "units": "10", "nano": 0},
                    {"currency": "USD", "units": "0", "nano": 0},
                ]
            }
        return {}

    monkeypatch.setattr(adapter, "_post", fake_post)

    balances = adapter.fetch_balances()
    assert len(balances) == 1
    assert balances[0].currency == "RUB"
    assert balances[0].total == 10.0


def test_tinkoff_adapter_resolves_instruments(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)
    instrument_calls = {"count": 0}

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {"accounts": [{"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"}]}
        if "GetPortfolio" in path:
            return {
                "positions": [
                    {
                        "figi": "FIGI123",
                        "instrumentType": "share",
                        "quantity": {"units": "2", "nano": 0},
                        "currentPrice": {"currency": "USD", "units": 10, "nano": 0},
                    }
                ]
            }
        if "GetInstrumentBy" in path:
            instrument_calls["count"] += 1
            return {"instrument": {"figi": payload.get("id"), "ticker": "TCS", "classCode": "MOEX"}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(adapter, "_post", fake_post)

    positions = adapter.fetch_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "TCS.MOEX"
    assert positions[0].quantity == 2.0
    assert positions[0].average_price == 10.0
    assert positions[0].currency == "USD"
    assert instrument_calls["count"] == 1


def test_tinkoff_adapter_caches_instrument_resolution(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)
    instrument_calls = {"count": 0}

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {
                "accounts": [
                    {"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"},
                    {"id": "acc2", "status": "ACCOUNT_STATUS_OPEN"},
                ]
            }
        if "GetPortfolio" in path:
            return {
                "positions": [
                    {
                        "figi": "FIGI456",
                        "instrumentType": "share",
                        "quantity": {"units": "1", "nano": 0},
                        "currentPrice": {"currency": "USD", "units": 100, "nano": 0},
                    }
                ]
            }
        
        if "GetInstrumentBy" in path:
            instrument_calls["count"] += 1
            return {"instrument": {"figi": payload.get("id"), "ticker": "ABC"}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(adapter, "_post", fake_post)

    positions = adapter.fetch_positions()
    assert len(positions) == 2  # one per account
    assert all(pos.symbol == "ABC" for pos in positions)
    assert instrument_calls["count"] == 1


def test_tinkoff_adapter_uses_current_price_as_average(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {"accounts": [{"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"}]}
        if "GetPortfolio" in path:
            return {
                "positions": [
                    {
                        "figi": "FIGI789",
                        "instrumentType": "bond",
                        "quantity": {"units": "4", "nano": 0},
                        "currentPrice": {"currency": "USD", "units": 100, "nano": 0},
                        "averagePositionPrice": {"currency": "USD", "units": 90, "nano": 0},
                    }
                ]
            }
        if "GetInstrumentBy" in path:
            return {"instrument": {"figi": payload.get("id"), "ticker": "BOND"}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(adapter, "_post", fake_post)

    positions = adapter.fetch_positions()
    assert len(positions) == 1
    # Should use currentPrice (100) not averagePositionPrice (90)
    assert positions[0].average_price == 100.0


def test_tinkoff_adapter_falls_back_to_avg_price_if_current_zero(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {"accounts": [{"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"}]}
        if "GetPortfolio" in path:
            return {
                "positions": [
                    {
                        "figi": "FIGI999",
                        "instrumentType": "share",
                        "quantity": {"units": "1", "nano": 0},
                        "currentPrice": {"currency": "USD", "units": 0, "nano": 0},
                        "averagePositionPrice": {"currency": "USD", "units": 5, "nano": 0},
                    }
                ]
            }
        if "GetInstrumentBy" in path:
            return {"instrument": {"figi": payload.get("id"), "ticker": "FALLBACK"}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(adapter, "_post", fake_post)

    positions = adapter.fetch_positions()
    assert len(positions) == 1
    assert positions[0].average_price == 5.0

