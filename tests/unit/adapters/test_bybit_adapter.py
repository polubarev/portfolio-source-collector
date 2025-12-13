from portfolio_source_collector.adapters.bybit import BybitAdapter
from portfolio_source_collector.core.config import BybitConfig


def test_bybit_balances_split_by_account_types(monkeypatch) -> None:
    config = BybitConfig(api_key="k", api_secret="s")
    adapter = BybitAdapter(config=config, client=None)

    def fake_get(path: str, params: dict | None = None) -> dict:
        params = params or {}
        if "wallet-balance" in path:
            account_type = params.get("accountType")
            if account_type == "UNIFIED":
                return {
                    "result": {
                        "list": [
                            {
                                "coin": [
                                    {"coin": "USDT", "walletBalance": "1.5", "availableToWithdraw": "1"},
                                    {"coin": "KAS", "walletBalance": "0.5", "availableToWithdraw": "0"},
                                ]
                            }
                        ]
                    }
                }
            if account_type == "INVESTMENT":
                return {
                    "result": {
                        "list": [
                            {"coin": [{"coin": "USDT", "walletBalance": "4", "availableToWithdraw": "4"}]}
                        ]
                    }
                }
        if "query-account-coin-balance" in path:
            acct = params.get("accountType")
            if acct == "FUND":
                return {"result": {"balance": [{"coin": "USDT", "transferBalance": "2"}]}}
            if acct == "EARN":
                return {"result": {"balance": [{"coin": "USDT", "transferBalance": "3"}]}}
        raise AssertionError(f"Unexpected path {path}")

    monkeypatch.setattr(adapter, "_get", fake_get)

    balances = adapter.fetch_balances()
    assert {b.account_type for b in balances} == {"unified_trading", "funding", "earn"}
    assert sum(1 for b in balances if b.currency == "USDT") == 4


def test_bybit_positions_fetch_all_types(monkeypatch) -> None:
    config = BybitConfig(api_key="k", api_secret="s")
    adapter = BybitAdapter(config=config, client=None)

    def fake_get(path: str, params: dict | None = None) -> dict:
        params = params or {}
        # Union of logic for wallet and transfer
        account = params.get("accountType")
        
        if "wallet-balance" in path:
            if account == "UNIFIED":
                return {
                    "result": {
                        "list": [
                            {"coin": [{"coin": "USDT", "walletBalance": "10", "equity": "10"}]}
                        ]
                    }
                }
        
        if "earn/position" in path:
             # Just return some result to simulate success
             return {
                "result": {
                    "list": [
                        {"coin": "BTC", "amount": "0.1"},
                    ]
                }
            }

        if "transfer/query-account-coin-balance" in path:
            if account == "FUND":
                return {
                    "result": {
                        "balance": [{"coin": "USDC", "walletBalance": "50"}]
                    }
                }
        
        return {}

    monkeypatch.setattr(adapter, "_get", fake_get)

    positions = adapter.fetch_positions()
    
    # Check types
    types = {p.account_type for p in positions}
    assert "unified_trading" in types
    assert "earn" in types
    assert "funding" in types
    
    # Check values
    total_qty = sum(p.quantity for p in positions)
    assert total_qty == 60.1  # 10 USDT + 50 USDC + 0.1 BTC
