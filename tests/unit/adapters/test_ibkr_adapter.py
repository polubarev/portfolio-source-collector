from portfolio_source_collector.adapters.interactive_brokers import InteractiveBrokersAdapter
from portfolio_source_collector.core.config import IBKRConfig


def test_ibkr_adapter_parses_ledger(monkeypatch) -> None:
    config = IBKRConfig(client_id="id", client_secret="secret", base_url="http://localhost")
    adapter = InteractiveBrokersAdapter(config=config, client=None)

    def fake_get(path: str) -> dict | list[dict]:
        if path.endswith("/portfolio/accounts"):
            return [{"id": "acct1"}]
        if "/ledger" in path:
            return {
                "USD": {"cashbalance": 12.5},
                "EUR": {"cashbalance": 0},
            }
        return {}

    monkeypatch.setattr(adapter, "_get", fake_get)

    balances = adapter.fetch_balances()
    assert len(balances) == 1
    assert balances[0].currency == "USD"
    assert balances[0].total == 12.5
