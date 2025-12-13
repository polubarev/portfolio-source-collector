from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Broker(str, Enum):
    TINKOFF = "tinkoff"
    BYBIT = "bybit"
    BINANCE = "binance"
    INTERACTIVE_BROKERS = "interactive_brokers"


class Balance(BaseModel):
    broker: Broker
    currency: str = Field(description="ISO currency code, e.g., USD")
    available: float = Field(description="Available amount for trading")
    total: float = Field(description="Total amount including locked funds")
    account_type: Optional[str] = Field(
        default=None, description="Optional broker-specific account type label."
    )


class Position(BaseModel):
    broker: Broker
    symbol: str
    quantity: float
    average_price: Optional[float] = None
    currency: Optional[str] = None
    account_type: Optional[str] = Field(
        default=None, description="Optional broker-specific account type label."
    )
