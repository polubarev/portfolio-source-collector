from __future__ import annotations

from typing import Iterable

import httpx

from portfolio_source_collector.core.config import Settings
from portfolio_source_collector.core.http import create_http_client
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.utils.currency import is_stable

logger = configure_logging(logger_name=__name__)


class PriceService:
    """
    Fetch USD prices for symbols using public exchange endpoints.
    Currently supports Binance and Bybit spot tickers; intended as a best-effort helper
    to reduce usd=n/a in the CLI when no avg_price or FX rate is present.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        # Generic client for public endpoints; base_url is set per call.
        self._client = client or create_http_client()

    def fetch_usd_prices(self, symbols: Iterable[str]) -> dict[str, float]:
        price_map: dict[str, float] = {}
        candidates = {s.upper() for s in symbols if s}
        if not candidates:
            return price_map

        # Stable assets are 1:1 USD by definition.
        for sym in list(candidates):
            if is_stable(sym):
                price_map[sym] = 1.0
                candidates.discard(sym)

        if not candidates:
            return price_map

        unresolved = set(candidates)
        binance_prices = self._fetch_binance_prices(unresolved)
        price_map.update(binance_prices)
        unresolved -= set(binance_prices)

        if unresolved:
            bybit_prices = self._fetch_bybit_prices(unresolved)
            price_map.update(bybit_prices)
            unresolved -= set(bybit_prices)

        if unresolved:
            logger.debug("PriceService could not resolve prices for: %s", sorted(unresolved))

        return price_map

    def _fetch_binance_prices(self, symbols: set[str]) -> dict[str, float]:
        results: dict[str, float] = {}
        if not symbols:
            return results

        base_url = self._settings.binance.base_url if self._settings.binance else "https://api.binance.com"
        # Standard quotes
        pairs = ["USDT", "USDC", "USD", "BUSD"]

        for symbol in symbols:
            price = None
            found_pair = ""
            
            # 1. Try BaseQuote (e.g. BTCUSDT)
            for quote in pairs:
                pair = f"{symbol}{quote}"
                try:
                    response = self._client.get(f"{base_url}/api/v3/ticker/price", params={"symbol": pair})
                    response.raise_for_status()
                    data = response.json()
                    raw_price = data.get("price")
                    price = float(raw_price)
                    found_pair = pair
                    break
                except Exception:
                    continue
            
            # 2. If failures and symbol is fiat-like (e.g. RUB), try Inverse (e.g. USDTRUB)
            if price is None and symbol == "RUB":
                # Try finding USDT/RUB or similar and invert
                for quote in ["USDT", "BUSD", "USDC"]:
                    pair = f"{quote}{symbol}"
                    try:
                        response = self._client.get(f"{base_url}/api/v3/ticker/price", params={"symbol": pair})
                        response.raise_for_status()
                        data = response.json()
                        raw_price = data.get("price")
                        # Inverse: 1 USDT = X RUB -> 1 RUB = 1/X USD
                        price = 1.0 / float(raw_price)
                        logger.info(f"Resolved {symbol} price via inverse pair {pair}: {price}")
                        break
                    except Exception:
                        continue

            if price is not None:
                results[symbol] = price
        return results

    def _fetch_bybit_prices(self, symbols: set[str]) -> dict[str, float]:
        results: dict[str, float] = {}
        if not symbols:
            return results

        base_url = self._settings.bybit.base_url if self._settings.bybit else "https://api.bybit.com"
        pairs = ["USDT", "USDC", "USD"]

        for symbol in symbols:
            price = None
            for quote in pairs:
                pair = f"{symbol}{quote}"
                try:
                    response = self._client.get(
                        f"{base_url}/v5/market/tickers",
                        params={"category": "spot", "symbol": pair},
                    )
                    response.raise_for_status()
                    data = response.json()
                    tickers = data.get("result", {}).get("list") or []
                    if not tickers:
                        continue
                    raw_price = tickers[0].get("lastPrice")
                    price = float(raw_price)
                    break
                except Exception:
                    continue
            if price is not None:
                results[symbol] = price
        return results
