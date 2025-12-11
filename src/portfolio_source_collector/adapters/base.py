from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from portfolio_source_collector.models import Balance, Position


class BrokerAdapter(ABC):
    """Abstract interface for broker adapters."""

    @abstractmethod
    def fetch_balances(self) -> Sequence[Balance]:
        """Return normalized balances for the broker."""

    @abstractmethod
    def fetch_positions(self) -> Sequence[Position]:
        """Return normalized open positions for the broker."""

