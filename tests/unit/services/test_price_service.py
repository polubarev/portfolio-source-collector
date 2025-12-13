from portfolio_source_collector.core.config import Settings
from portfolio_source_collector.services.price_service import PriceService


def test_price_service_handles_stable_and_binance(monkeypatch) -> None:
    settings = Settings()
    service = PriceService(settings=settings, client=None)

    calls = {"binance": 0, "bybit": 0}

    def fake_binance(symbols: set[str]) -> dict[str, float]:
        calls["binance"] += 1
        assert symbols == {"BNB"}
        return {"BNB": 200.0}

    def fake_bybit(symbols: set[str]) -> dict[str, float]:
        calls["bybit"] += 1
        return {}

    monkeypatch.setattr(service, "_fetch_binance_prices", fake_binance)
    monkeypatch.setattr(service, "_fetch_bybit_prices", fake_bybit)

    prices = service.fetch_usd_prices({"usdt", "BNB"})
    assert prices["USDT"] == 1.0  # stable coin shortcut
    assert prices["BNB"] == 200.0
    assert calls["binance"] == 1
    assert calls["bybit"] == 0  # not called because all resolved


def test_price_service_falls_back_to_bybit(monkeypatch) -> None:
    settings = Settings()
    service = PriceService(settings=settings, client=None)

    calls = {"binance": 0, "bybit": 0}

    def fake_binance(symbols: set[str]) -> dict[str, float]:
        calls["binance"] += 1
        return {}

    def fake_bybit(symbols: set[str]) -> dict[str, float]:
        calls["bybit"] += 1
        assert symbols == {"LUNA"}
        return {"LUNA": 0.5}

    monkeypatch.setattr(service, "_fetch_binance_prices", fake_binance)
    monkeypatch.setattr(service, "_fetch_bybit_prices", fake_bybit)

    prices = service.fetch_usd_prices({"luna"})
    assert prices["LUNA"] == 0.5
    assert calls["binance"] == 1
    assert calls["bybit"] == 1
