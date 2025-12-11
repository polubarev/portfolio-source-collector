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
   - `IBKR_CLIENT_ID`, `IBKR_CLIENT_SECRET`, `IBKR_BASE_URL` (point to your Client Portal Gateway, e.g., `https://localhost:5000`), optional `IBKR_ACCOUNT_ID`/`IBKR_ACCOUNT_IDS`
4. Run the CLI:
   ```bash
   portfolio-balances --help
   ```

## Implementation Notes
- Binance and Bybit adapters include signing and wallet balance normalization; positions are still TODO. Tinkoff uses `GetPositions` money block; IBKR uses the Client Portal Gateway ledger endpoint (gateway must be running and authenticated).
- Adapters normalize into the shared `Balance` model with currency codes and amounts.
- Add per-broker rate limiting/backoff in `core/http.py` and extend error handling for throttling/auth failures.
- Prefer not to log secrets; centralize signing/auth in each adapter.
- Add unit tests with recorded fixtures; avoid live API calls in CI.
