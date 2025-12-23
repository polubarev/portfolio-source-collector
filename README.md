# Portfolio Source Collector

Fetch balances across multiple brokers (Tinkoff Investments, Bybit, Binance, Interactive Brokers) through a common interface.

## Structure
- `src/portfolio_source_collector/core`: shared config, logging, HTTP client, error definitions.
- `src/portfolio_source_collector/models`: Pydantic models for brokers, balances, positions, currencies.
- `src/portfolio_source_collector/adapters`: one adapter per broker exposing a uniform API.
- `src/portfolio_source_collector/services`: orchestration and aggregation of balances.
- `src/portfolio_source_collector/cli`: Typer-based CLI entrypoints.
- `src/portfolio_source_collector/utils`: helpers (time, math, currency).
- `config`: `.env.example`, `config.example.yaml` with placeholders for secrets/IDs.
- `tests`: unit tests with fixtures for adapter payloads.

## Getting Started
1. Install Python 3.10+ and create a virtual environment.
2. Install dependencies:
   ```bash
   pip install -e '.[dev]'
   ```
3. Copy `config/.env.example` to `.env` and fill in API keys/secrets:
   - `TINKOFF_TOKEN`
   - `TINKOFF_ACCOUNT_ID` or `TINKOFF_ACCOUNT_IDS` (comma-separated) if you want to target specific accounts.
   - `BYBIT_API_KEY`, `BYBIT_API_SECRET`
   - `BINANCE_API_KEY`, `BINANCE_API_SECRET`
   - `IBKR_HOST` (default `127.0.0.1`), `IBKR_PORT` (e.g., `7497` for paper), `IBKR_CLIENT_ID`, optional `IBKR_ACCOUNT_ID`/`IBKR_ACCOUNT_IDS` (IB socket API), `IBKR_API_PATH` if ibapi isn’t installed system-wide.
4. Run the CLI:
   ```bash
   portfolio-balances --show-positions
   ```

### Interactive Brokers (ibapi) setup
- Download the IB API bundle (e.g., `twsapi_macunix.1037.02.zip`) from IBKR and unzip it in the repo root (already present in this repo).
- Install the python client into your venv:
  ```bash
  pip install twsapi_macunix.1037.02/IBJts/source/pythonclient
  ```
  or set `IBKR_API_PATH` in `.env` to point to `.../twsapi_macunix.1037.02/IBJts/source/pythonclient` so the adapter can import `ibapi` without installation.
- Ensure TWS or IB Gateway is running, API is enabled, and ports/clientId match your `.env` (`IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`).

## Implementation Notes
- Binance and Bybit adapters include signing and wallet balance normalization; positions include wallet holdings, and Binance also pulls Simple Earn positions (flexible/locked) when available. Tinkoff uses `GetPositions` money block; IBKR uses the socket API (TWS/IB Gateway) to fetch cash and positions (ensure TWS/Gateway is running and logged in).
- Adapters normalize into the shared `Balance` model with currency codes and amounts.
- Add per-broker rate limiting/backoff in `core/http.py` and extend error handling for throttling/auth failures.
- Prefer not to log secrets; centralize signing/auth in each adapter.
- Add unit tests with recorded fixtures; avoid live API calls in CI.
