from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.models import Balance, Broker, Position
from portfolio_source_collector.services import BalanceService


class DummyAdapter(BrokerAdapter):
    def fetch_balances(self) -> list[Balance]:
        return [Balance(broker=Broker.BINANCE, currency="USD", available=1.0, total=1.0)]

    def fetch_positions(self) -> list[Position]:
        return [
            Position(broker=Broker.BINANCE, symbol="BTC", quantity=1.0, average_price=10000.0),
        ]


def test_balance_service_uses_injected_adapters() -> None:
    service = BalanceService(adapters=[DummyAdapter()])
    balances = service.fetch_all()
    assert balances and balances[0].total == 1.0


def test_balance_service_positions_injected() -> None:
    service = BalanceService(adapters=[DummyAdapter()])
    positions = service.fetch_positions()
    assert positions and positions[0].symbol == "BTC"
