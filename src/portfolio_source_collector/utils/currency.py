from __future__ import annotations

from typing import Optional


def convert(amount: float, rate: Optional[float]) -> float:
    """
    Convert an amount using a provided FX rate.
    Caller is responsible for fetching rates; this helper keeps math centralized.
    """
    if rate is None:
        return amount
    return amount * rate

