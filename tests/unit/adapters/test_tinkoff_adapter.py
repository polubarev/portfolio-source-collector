from portfolio_source_collector.adapters.tinkoff import TinkoffAdapter
from portfolio_source_collector.core.config import TinkoffConfig


def test_tinkoff_adapter_parses_money_balances(monkeypatch) -> None:
    config = TinkoffConfig(token="token", account_id=None, account_ids=[])
    adapter = TinkoffAdapter(config=config, client=None)

    def fake_post(path: str, payload: dict | None = None) -> dict:
        if "GetAccounts" in path:
            return {"accounts": [{"id": "acc1", "status": "ACCOUNT_STATUS_OPEN"}]}
        if "GetPositions" in path:
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
