from __future__ import annotations

import json
from typing import Optional

import typer

from portfolio_source_collector.core.config import get_settings
from portfolio_source_collector.core.logging import configure_logging
from portfolio_source_collector.services import BalanceService

app = typer.Typer(add_completion=False, no_args_is_help=True)
logger = configure_logging(logger_name=__name__)


@app.command()
def balances(format: Optional[str] = typer.Option("table", help="table or json")) -> None:
    """Fetch balances across all configured brokers."""
    settings = get_settings()
    service = BalanceService(settings=settings)
    data = service.fetch_all()

    if not data:
        typer.echo("No balances fetched; ensure credentials are configured.")
        return

    if format == "json":
        typer.echo(json.dumps([balance.model_dump() for balance in data], indent=2))
        return

    for balance in data:
        typer.echo(
            f"{balance.broker.value:22} {balance.currency:5} "
            f"available={balance.available:.2f} total={balance.total:.2f}"
        )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
