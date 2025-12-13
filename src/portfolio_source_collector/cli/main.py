from __future__ import annotations

import json
from typing import Optional

import typer

from portfolio_source_collector.core.config import get_settings
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.services import BalanceService, PriceService
from portfolio_source_collector.utils.currency import STABLE_COINS, is_stable, to_usd

app = typer.Typer(add_completion=False, no_args_is_help=True)
logger = configure_logging(logger_name=__name__)


def _fmt_amount(value: float, precision: int = 8) -> str:
    formatted = f"{value:.{precision}f}"
    formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _with_account(label: str, account_type: Optional[str]) -> str:
    if not account_type:
        return label
    return f"{label} [{account_type}]"


def _position_value_usd(pos, fx_rates: dict[str, float]) -> Optional[float]:
    # If average_price known, multiply then convert.
    if pos.average_price is not None and pos.currency:
        return to_usd(pos.average_price * pos.quantity, pos.currency, fx_rates)
    # If currency is USD stable, assume price=1.
    if pos.currency and pos.currency.upper() in STABLE_COINS:
        return pos.quantity
    # Fall back to symbol for stables (e.g., when currency is missing).
    if pos.currency is None and is_stable(pos.symbol):
        return pos.quantity
    return None


@app.command()
def balances(
    format: Optional[str] = typer.Option("table", help="table or json"),
    show_positions: bool = typer.Option(False, help="Include positions/assets"),
) -> None:
    """Fetch balances (and optionally positions) across all configured brokers."""
    settings = get_settings()
    fx_rates = settings.fx_rates or {}
    service = BalanceService(settings=settings)
    data = service.fetch_all()
    positions = service.fetch_positions() if show_positions else []
    price_service = PriceService(settings=settings)

    if not data and not positions:
        typer.echo("No balances fetched; ensure credentials are configured.")
        return

    # Prepare symbol list for price lookup (best-effort).
    symbols_for_prices: set[str] = set()
    for balance in data:
        if to_usd(balance.total, balance.currency, fx_rates) is None and not is_stable(
            balance.currency
        ):
            symbols_for_prices.add(balance.currency)
    for pos in positions:
        if _position_value_usd(pos, fx_rates) is None and pos.symbol:
            symbols_for_prices.add(pos.symbol)
    price_map = price_service.fetch_usd_prices(symbols_for_prices)
    
    # Inject resolved prices for currencies into fx_rates so to_usd() works
    for symbol, price in price_map.items():
        # If symbol is used as a currency (e.g. RUB), add it to fx_rates
        # We can be aggressive here: if it's in price_map, it's a USD rate.
        if symbol not in fx_rates:
            fx_rates[symbol] = price

    if format == "json":
        balances_payload = []
        for balance in data:
            entry = balance.model_dump()
            usd_value = to_usd(balance.total, balance.currency, fx_rates)
            if usd_value is None:
                usd_value = price_map.get(balance.currency.upper())
                if usd_value is not None:
                    usd_value *= balance.total
            entry["value_usd"] = usd_value
            balances_payload.append(entry)
        positions_payload = []
        for pos in positions:
            entry = pos.model_dump()
            usd_value = _position_value_usd(pos, fx_rates)
            if usd_value is None and pos.symbol:
                price = price_map.get(pos.symbol.upper())
                if price is not None:
                    usd_value = pos.quantity * price
            entry["value_usd"] = usd_value
            positions_payload.append(entry)
        payload: dict[str, list[dict]] = {"balances": balances_payload}
        if positions:
            payload["positions"] = positions_payload
        typer.echo(json.dumps(payload, indent=2))
        return

    # Sort by broker to group outputs.
    data_sorted = sorted(data, key=lambda b: b.broker.value)
    positions_sorted = sorted(positions, key=lambda p: p.broker.value) if positions else []

    # Group by broker and print balances then positions per broker.
    brokers = sorted(
        {b.broker for b in data_sorted}.union({p.broker for p in positions_sorted}),
        key=lambda x: x.value,
    )
    for broker in brokers:
        typer.echo(f"[{broker.value}]")
        broker_positions = [p for p in positions_sorted if p.broker == broker]
        
        # For Crypto brokers (Binance, Bybit), positions output is a superset of balances.
        # To avoid duplication, if positions are shown, suppress the balances section.
        show_balances = True
        if broker.value in ["binance", "bybit"] and broker_positions:
            show_balances = False

        broker_balances = [b for b in data_sorted if b.broker == broker]
        if broker_balances and show_balances:
            typer.echo("  Balances:")
            for balance in broker_balances:
                usd_value = to_usd(balance.total, balance.currency, fx_rates)
                if usd_value is None:
                    price = price_map.get(balance.currency.upper())
                    if price is not None:
                        usd_value = balance.total * price
                usd_str = f" usd≈{usd_value:.2f}" if usd_value is not None else " usd=n/a"
                label = _with_account(balance.currency, balance.account_type)
                typer.echo(
                    f"    {label:12} available={_fmt_amount(balance.available)} "
                    f"total={_fmt_amount(balance.total)}{usd_str}"
                )
        broker_positions = [p for p in positions_sorted if p.broker == broker]
        if broker_positions:
            typer.echo("  Positions:")
            for pos in broker_positions:
                usd_value = _position_value_usd(pos, fx_rates)
                if usd_value is None and pos.symbol:
                    price = price_map.get(pos.symbol.upper())
                    if price is not None:
                        usd_value = pos.quantity * price
                usd_str = f" usd≈{usd_value:.2f}" if usd_value is not None else " usd=n/a"
                label = _with_account(pos.symbol, pos.account_type)
                typer.echo(
                    f"    {label:12} qty={_fmt_amount(pos.quantity)} "
                    f"avg_price={_fmt_amount(pos.average_price or 0)} {pos.currency or ''}{usd_str}"
                )
        typer.echo("")


def main() -> None:
    app()


if __name__ == "__main__":
    main()


def _position_value_usd(pos, fx_rates: dict[str, float]) -> Optional[float]:
    # If average_price known, multiply then convert.
    if pos.average_price is not None and pos.currency:
        return to_usd(pos.average_price * pos.quantity, pos.currency, fx_rates)
    # If currency is USD stable, assume price=1.
    if pos.currency and pos.currency.upper() in STABLE_COINS:
        return pos.quantity
    return None
