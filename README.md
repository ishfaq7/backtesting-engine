# btengine — CoinGlass Data Layer

This repository currently implements **only the CoinGlass data layer** of
the broader backtesting platform. See `docs/ARCHITECTURE.md` and
`docs/STRATEGY_AND_DATA_LAYER.md` for the full system design; this module
is the first piece built from that design.

It does **not** contain the Strategy Engine, the Backtesting Engine, or any
GUI — only historical market data acquisition, validation, normalization,
and local caching.

## What's here

- An authenticated, rate-limited, retrying CoinGlass API client.
- Validation of every raw response before it is trusted.
- Normalization of CoinGlass's response shape into a canonical,
  provider-agnostic schema (`btengine.data.schema`).
- A local Parquet+DuckDB cache to avoid re-fetching already-known data.
- A historical data loader that fetches only missing sub-ranges and
  surfaces missing candles/records as explicit gaps.
- Structured, typed errors everywhere — no bare `Exception`, no silent
  failures.

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
from btengine.data.sync import DataSyncService

provider = build_coinglass_provider()          # reads COINGLASS_API_KEY etc. from env
repository = DataRepository("./data_cache")
sync = DataSyncService(provider, repository)

end = datetime.now(timezone.utc)
start = end - timedelta(days=7)

candles = sync.ensure_ohlcv(
    exchange="binance", symbol="BTCUSDT", timeframe=Timeframe.HOUR_1, start=start, end=end
)
```

The first call fetches from CoinGlass and populates the cache; subsequent
calls for the same range are served from disk with zero API requests.

## Testing

```bash
pytest -q --cov=btengine --cov-report=term-missing
```

## Project layout

See the end-of-task summary in the project conversation history (or
`docs/STRATEGY_AND_DATA_LAYER.md` §6) for the full folder structure and
per-file responsibilities.
