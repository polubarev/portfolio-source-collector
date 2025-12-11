from portfolio_source_collector.adapters.bybit import BybitAdapter
from portfolio_source_collector.core.config import BybitConfig


def test_bybit_adapter_handles_empty_strings(monkeypatch) -> None:
    config = BybitConfig(api_key="key", api_secret="secret")
    adapter = BybitAdapter(config=config, client=None)

    sample = {
        "result": {
            "list": [
                {
                    "coin": [
                        {
                            "coin": "BTC",
                            "walletBalance": "0.00668",
                            "availableToWithdraw": "",
                        },
                        {"coin": "USDT", "walletBalance": "0", "availableToWithdraw": "0"},
                    ]
                }
            ]
        }
    }

    monkeypatch.setattr(adapter, "_get", lambda path, params=None: sample)

    balances = adapter.fetch_balances()
    assert len(balances) == 1
    assert balances[0].currency == "BTC"
    assert balances[0].available == 0.0
    assert balances[0].total == 0.00668
