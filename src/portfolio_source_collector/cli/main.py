from __future__ import annotations

import json
from typing import Optional

import typer

from portfolio_source_collector.core.config import get_settings
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.services import BalanceService
from portfolio_source_collector.utils.currency import STABLE_COINS, to_usd

app = typer.Typer(add_completion=False, no_args_is_help=True)
logger = configure_logging(logger_name=__name__)


def _position_value_usd(pos, fx_rates: dict[str, float]) -> Optional[float]:
    # If average_price known, multiply then convert.
    if pos.average_price is not None and pos.currency:
        return to_usd(pos.average_price * pos.quantity, pos.currency, fx_rates)
    # If currency is USD stable, assume price=1.
    if pos.currency and pos.currency.upper() in STABLE_COINS:
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

    if not data and not positions:
        typer.echo("No balances fetched; ensure credentials are configured.")
        return

    if format == "json":
        balances_payload = []
        for balance in data:
            entry = balance.model_dump()
            entry["value_usd"] = to_usd(balance.total, balance.currency, fx_rates)
            balances_payload.append(entry)
        positions_payload = []
        for pos in positions:
            entry = pos.model_dump()
            entry["value_usd"] = _position_value_usd(pos, fx_rates)
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
        broker_balances = [b for b in data_sorted if b.broker == broker]
        if broker_balances:
            typer.echo("  Balances:")
            for balance in broker_balances:
                usd_value = to_usd(balance.total, balance.currency, fx_rates)
                usd_str = f" usd≈{usd_value:.2f}" if usd_value is not None else " usd=n/a"
                typer.echo(
                    f"    {balance.currency:5} available={balance.available:.2f} total={balance.total:.2f}{usd_str}"
                )
        broker_positions = [p for p in positions_sorted if p.broker == broker]
        if broker_positions:
            typer.echo("  Positions:")
            for pos in broker_positions:
                usd_value = _position_value_usd(pos, fx_rates)
                usd_str = f" usd≈{usd_value:.2f}" if usd_value is not None else " usd=n/a"
                typer.echo(
                    f"    {pos.symbol:10} qty={pos.quantity:.4f} "
                    f"avg_price={pos.average_price or 0:.4f} {pos.currency or ''}{usd_str}"
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
