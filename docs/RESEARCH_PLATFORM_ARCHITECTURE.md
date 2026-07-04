# Research Platform Architecture Extension

Status: **Architecture and folder-structure upgrade only.** Every module
listed here is new; **no existing file was modified** (verified: `git diff`
against the prior commit touches only new paths). This document extends
`docs/ARCHITECTURE.md` and `docs/STRATEGY_AND_DATA_LAYER.md` with 16
additional capabilities for future quantitative research, backward
compatible by construction since nothing existing changed.

## 1. Two kinds of "not implemented yet"

Every new package below falls into one of two buckets, and the split is
deliberate:

- **Infrastructure/orchestration (fully implemented and tested).** Things
  that store data, split date ranges, run existing components multiple
  times, or report on already-computed results contain no market
  interpretation or trading decision — they're plumbing, the same category
  as the Data Layer's cache or the Core Engine's event queue. These are
  real, working, tested code.
- **Market-interpretation analyzers (interface-only).** ATR, CVD, and
  Market Structure each *compute a value that interprets what the market is
  doing* — the same category as the indicators the Core Backtesting Engine
  was explicitly told to exclude, and the same category as the proprietary
  analyzers reserved for the strategy plugin in
  `docs/STRATEGY_AND_DATA_LAYER.md`. These get an abstract contract
  (`FeatureAnalyzer`) and a class shell that raises `NotImplementedError` —
  the shape is fixed, the calculation is not, pending explicit approval.

This mirrors exactly how prior phases of this project have worked: design
→ approval → implementation, one bounded piece at a time.

## 2. Folder structure added

```
src/btengine/
├── data/                    (existing, untouched)
├── strategy/                (existing files untouched; two new files added)
│   ├── base.py                  (existing)
│   ├── context.py               (existing)
│   ├── versioning.py            NEW - StrategyVersion, StrategyRegistry
│   └── profiles.py              NEW - StrategyProfileName, StrategyProfile
├── backtest/                (existing, untouched)
├── features/                NEW package - Feature Engineering Layer
│   ├── base.py                  FeatureValue, HistoricalCandleSource, FeatureAnalyzer (ABC)
│   ├── multi_timeframe.py       MultiTimeframeView (full) - #1 Multi-Timeframe Analysis
│   ├── market_structure.py      MarketStructureAnalyzer (interface only) - #4
│   ├── atr.py                   ATRAnalyzer (interface only) - #5
│   └── cvd.py                   CVDAnalyzer (interface only, provider-independent) - #6
├── feature_store/            NEW package - #3 Feature Store
│   ├── errors.py
│   ├── base.py                  FeatureStore (ABC)
│   └── local_store.py           LocalFeatureStore (full, Parquet+DuckDB)
├── research/                  NEW package - quantitative research tooling
│   ├── errors.py
│   ├── walk_forward.py          WalkForwardSplitter (full) - #8 Walk-Forward Testing
│   ├── monte_carlo.py           MonteCarloValidator (full) - #9 Monte Carlo Validation
│   ├── batch_backtest.py        BatchBacktestRunner (full) - #11 Batch Backtesting
│   ├── portfolio_backtest.py    PortfolioBacktestRunner (full) - #12 Portfolio Backtesting
│   └── parallel_backtest.py     run_multi_coin_backtest (full) - #13 Multi-Coin Parallel Backtesting
└── integrations/              NEW package - forward-looking seams
    ├── ai_model.py               AIModelProvider Protocol - #14 Future AI Model Integration
    ├── live_trading.py           LiveMarketDataFeed / LiveExecutionHandler Protocols - #15
    └── web_dashboard.py          DashboardPublisher Protocol - #16
```

`#2 Feature Engineering Layer` and `#7 Strategy Versioning` and
`#10 Strategy Profiles` are the *packages/modules themselves* (`features/`
as a whole, and the two new `strategy/` files), not a single class — see
their sections below.

## 3. Capability-by-capability design

### 1. Multi-Timeframe Analysis — `features/multi_timeframe.py`

`MultiTimeframeView` composes several existing, unmodified `HistoryView`
instances (one per `Timeframe`) behind one object, so code can read, say,
4h candles while a backtest trades on 15m — without touching
`StrategyContext`, `BacktestEngine`, or any existing file. Every
lookahead guarantee `HistoryView` already provides carries through
unchanged, since this is pure composition, not a new data path.

**Not yet wired in:** `StrategyContext` itself still only carries one
`HistoryView`. Adding an optional multi-timeframe field to it would
require editing `strategy/context.py`, which this pass does not touch.
For now, a strategy plugin (or a research script) constructs a
`MultiTimeframeView` independently via `build_multi_timeframe_view(...)`.

### 2. Feature Engineering Layer — `features/`

The package as a whole. `features/base.py` defines the shared contract:
`FeatureValue` (one named, timestamped, scalar result) and
`FeatureAnalyzer` (the ABC every feature computation implements — one
`feature_name`, one `compute(symbol, history) -> FeatureValue` method).
This mirrors the Strategy plugin's `MarketAnalyzer` role but is
positioned for *generic, reusable* computations, not proprietary logic.

### 3. Feature Store — `feature_store/`

`FeatureStore` (ABC) + `LocalFeatureStore` (a full, Parquet+DuckDB backed
implementation, deliberately re-implementing — not reusing — the pattern
already proven in `data/repository.py`, since modifying that file was out
of scope). Persists `FeatureAnalyzer` outputs so expensive computations
aren't repeated across research runs. One file per (symbol, feature_name),
idempotent merge-on-write, range reads via DuckDB — same proven shape as
the Data Layer's cache, applied to a different kind of data.

### 4/5/6. Market Structure / ATR / CVD Analyzers — `features/*.py`

Each is a `FeatureAnalyzer` subclass with `compute()` raising
`NotImplementedError`. CVD in particular surfaces an honest data-
availability gap in its docstring: a correct CVD needs taker buy/sell
volume, which the canonical `Candle` schema doesn't carry (only aggregate
volume) — CoinGlass does expose a taker buy/sell endpoint on the Startup
plan (noted as a future need in `docs/COINGLASS_INTEGRATION.md`) that a
real implementation would need to consume.

### 7. Strategy Versioning — `strategy/versioning.py`

`StrategyVersion` (name + version + description) and `StrategyRegistry`
(in-memory, register/get/list). Independent from the entry-point plugin
*discovery* mechanism in `docs/STRATEGY_AND_DATA_LAYER.md` — this only
lets any research result (a backtest, a walk-forward run, a Monte Carlo
validation) be traced back to exactly which strategy version produced it.

### 8. Walk-Forward Testing — `research/walk_forward.py`

`WalkForwardSplitter.split(start, end)` returns rolling
`(train_start, train_end, test_start, test_end)` windows. Pure date
arithmetic — it decides nothing about a strategy. Running the actual
in-sample/out-of-sample backtests per window (e.g. via
`BatchBacktestRunner`, one job per window) is the caller's job.

### 9. Monte Carlo Validation — `research/monte_carlo.py`

`MonteCarloValidator.validate(trades, initial_cash)` bootstraps N
alternative equity curves by resampling a completed backtest's
*already-recorded* `ClosedTrade` PnLs with replacement — a standard,
non-proprietary technique for separating order-dependent luck from robust
edge. It never re-runs the strategy or touches market data.

### 11. Batch Backtesting — `research/batch_backtest.py`

`BatchBacktestRunner` runs a list of `BacktestJob`s (each: name, config,
repository, a *factory* for a fresh `Strategy` instance) sequentially or
via a thread pool, returning a `BatchBacktestResult` per job — including
captured errors, so one bad config doesn't sink the batch. Built entirely
on the existing, unmodified `BacktestEngine`.

### 12. Portfolio Backtesting — `research/portfolio_backtest.py`

The existing `BacktestEngine` already runs a true shared-capital portfolio
backtest whenever `BacktestConfig.symbols` has more than one entry — its
`HistoricalCandleFeed` merges symbols into one chronological stream and
`PortfolioState` already sums PnL across every open position regardless of
symbol. `PortfolioBacktestRunner` adds only what's missing: a per-symbol
trade-level breakdown (`SymbolAttribution`) computed after the fact from
`BacktestResult.trades`. It deliberately does *not* report a per-symbol
"return," since attributing shared capital to one symbol would be
arbitrary.

### 13. Multi-Coin Parallel Backtesting — `research/parallel_backtest.py`

`run_multi_coin_backtest(...)` builds one *independent*,
separately-capitalized `BacktestConfig` per symbol and runs them through
`BatchBacktestRunner` — the opposite of portfolio backtesting: many
isolated runs, not one shared portfolio. Useful for screening many coins
with the same strategy.

### 10. Strategy Profiles — `strategy/profiles.py`

`StrategyProfileName` (`CONSERVATIVE` / `BALANCED` / `AGGRESSIVE`) and
`StrategyProfile` (a dataclass bundling `max_risk_per_trade_pct`,
`max_concurrent_positions`, `max_portfolio_exposure_pct`). Deliberately
ships with **no concrete numeric presets** — choosing actual risk
percentages per profile is a strategy decision, out of scope here. Only
the container shape is provided.

### 14/15/16. Future AI Model / Live Trading / Web Dashboard — `integrations/`

Three files, each a `typing.Protocol` (`@runtime_checkable`, so
`isinstance()` checks work against them): `AIModelProvider.predict(...)`,
`LiveMarketDataFeed.iter_live()` + `LiveExecutionHandler.submit_order(...)`
(mirroring `HistoricalCandleFeed` and `OrderManager`'s fill contract
exactly, so a live agent reuses everything else in the engine unchanged),
and `DashboardPublisher.publish_result(...)` /
`.publish_equity_point(...)` (consuming the engine's already-serializable
`BacktestResult`/equity curve). None are implemented; they exist only so
something can depend on the abstraction today.

## 4. Backward compatibility

Every item above is a new file in a new (or, for `strategy/`, an existing
but only additively-extended) package. Nothing in `data/`, `backtest/`,
`strategy/base.py`, or `strategy/context.py` changed. Every existing test
still passes unmodified. New code depends on existing code (e.g.
`BatchBacktestRunner` imports `BacktestEngine`); nothing existing depends
on anything new.

## 5. What's next (pending approval)

- Wiring `MultiTimeframeView` into `StrategyContext` (requires editing
  `strategy/context.py`).
- Implementing the ATR/CVD/Market Structure calculations themselves.
- Wiring `FeatureAnalyzer` output into the `BacktestEngine`'s per-tick loop
  (requires editing `backtest/engine.py`) so features are computed
  automatically alongside `StrategyContext` construction.
- Choosing concrete numeric values for the three `StrategyProfile` presets.
- Any concrete AI model, live exchange connection, or dashboard transport
  implementing the three `integrations/` Protocols.
