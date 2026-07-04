# btengine — CoinGlass Data Layer + Core Backtesting Engine

This repository currently implements the **CoinGlass data layer** and the
**core, event-driven Backtesting Engine** of the broader trading platform.
See `docs/ARCHITECTURE.md` and `docs/STRATEGY_AND_DATA_LAYER.md` for the
full system design.

It does **not** contain any concrete trading strategy, the Strategy
Engine's plugin ecosystem, GUI, Telegram integration, or live/demo trading
— only historical data acquisition/caching and a strategy-agnostic
simulation engine that a future strategy plugin will plug into via the
single `Strategy.on_market_event(context)` interface.

## What's here

**Data layer** (scoped to the CoinGlass **Startup** plan — see
`docs/COINGLASS_INTEGRATION.md`):
- An authenticated, rate-limited, retrying CoinGlass API client with
  automatic pagination (CoinGlass caps every response at 1000 rows) and
  connection verification (`verify_connection()`).
- Plan-aware request validation (`plan_limits.py`): rejects unsupported
  intervals or history lengths *before* any HTTP call.
- Validation of every raw response before it is trusted.
- Normalization of CoinGlass's response shape into a canonical,
  provider-agnostic schema (`btengine.data.schema`), including instrument
  discovery (`get_supported_markets()`).
- A local Parquet+DuckDB cache to avoid re-fetching already-known data.
- `HistoricalDataService`: the reusable, cache-first historical data
  loader meant to be shared by the Backtesting Engine, Demo Trading Agent,
  and Live Trading Agent alike. Fetches only missing sub-ranges and
  surfaces missing candles/records as explicit gaps.

**Core Backtesting Engine (`btengine.backtest`):**
- An event-driven simulation loop (`MarketEvent → SignalEvent → OrderEvent
  → FillEvent`) that processes candles strictly in chronological order.
- Structural lookahead prevention: a strategy's historical queries are
  hard-clipped to the current simulation time, and orders it triggers can
  only fill on the *next* bar, never the one that produced the signal.
- Netted position accounting, margin-style portfolio equity, trade
  recording, and summary performance metrics (drawdown, win rate, profit
  factor).
- Multi-asset support today (not just planned): candles from several
  symbols are merged into one chronological stream.

Structured, typed errors everywhere in both layers — no bare `Exception`,
no silent failures.

**Research platform extensions** (architecture/scaffolding only — see
`docs/RESEARCH_PLATFORM_ARCHITECTURE.md`): a Feature Engineering Layer and
Feature Store (`btengine.features`, `btengine.feature_store`), quant
research tooling (`btengine.research`: walk-forward splitting, Monte Carlo
validation, batch/portfolio/multi-coin backtesting), strategy versioning
and profile presets (new files in `btengine.strategy`), and forward-looking
Protocol seams for AI models, live trading, and a web dashboard
(`btengine.integrations`). None of this touched an existing file.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in COINGLASS_API_KEY
```

Never commit `.env`. `.env.example` documents every supported setting;
everything else has a sane default (see
`btengine.data.providers.coinglass.config.CoinGlassSettings`).

## Usage

```python
from datetime import datetime, timedelta, timezone

from btengine.data.providers.coinglass.provider import build_coinglass_provider
from btengine.data.repository import DataRepository
from btengine.data.schema import Timeframe
from btengine.data.sync import HistoricalDataService

provider = build_coinglass_provider()          # reads COINGLASS_API_KEY etc. from env
provider.verify_connection()                    # raises immediately if the key/connection is bad

repository = DataRepository("./data_cache")
historical_data = HistoricalDataService(provider, repository)

end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

candles = historical_data.ensure_ohlcv(
    exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1, start=start, end=end
)
```

The first call fetches from CoinGlass and populates the cache; subsequent
calls for the same range are served from disk with zero API requests.

Running a backtest (once data is cached) requires a `Strategy`
implementation — there isn't a real one yet, only the abstract interface
in `btengine.strategy.base`. See `docs/STRATEGY_AND_DATA_LAYER.md` for the
plugin design that will supply one.

## Testing

```bash
pytest -q --cov=btengine --cov-report=term-missing
```

## Project layout

See the end-of-task summary in the project conversation history (or
`docs/STRATEGY_AND_DATA_LAYER.md` §6) for the full folder structure and
per-file responsibilities.
