from __future__ import annotations

from typing import Optional

STABLE_COINS = {
    "USD",
    "USDT",
    "USDC",
    "BUSD",
    "DAI",
    "TUSD",
    "FDUSD",
    "USDD",
    "USDP",
}


def is_stable(symbol: str | None) -> bool:
    if not symbol:
        return False
    sym = symbol.upper()
    if sym in STABLE_COINS:
        return True
    # Heuristic: tokens that are clearly USD-pegged variants.
    if sym.endswith(("USD", "USDT", "USDC", "USDD", "BUSD", "TUSD")):
        return True
    return False


def convert(amount: float, rate: Optional[float]) -> float:
    """
    Convert an amount using a provided FX rate.
    Caller is responsible for fetching rates; this helper keeps math centralized.
    """
    if rate is None:
        return amount
    return amount * rate


def to_usd(amount: float, currency: str, fx_rates: dict[str, float]) -> Optional[float]:
    """
    Convert amount to USD if possible.
    - If currency is USD or a USD stable coin, returns amount.
    - If fx_rates contains a rate for the currency, applies it.
    - Otherwise returns None.
    """
    if is_stable(currency):
        return amount
    currency = currency.upper()
    rate = fx_rates.get(currency)
    if rate is None:
        return None
    return amount * rate
