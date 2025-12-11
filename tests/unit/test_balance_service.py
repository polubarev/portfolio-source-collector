from portfolio_source_collector.adapters.base import BrokerAdapter
from portfolio_source_collector.models import Balance, Broker, Position
from portfolio_source_collector.services import BalanceService


class DummyAdapter(BrokerAdapter):
    def fetch_balances(self) -> list[Balance]:
        return [Balance(broker=Broker.BINANCE, currency="USD", available=1.0, total=1.0)]

    def fetch_positions(self) -> list[Position]:
        return []


def test_balance_service_uses_injected_adapters() -> None:
    service = BalanceService(adapters=[DummyAdapter()])
    balances = service.fetch_all()
    assert balances and balances[0].total == 1.0
