# CoinGlass Data Layer & Strategy Framework — Architecture Design

Status: **Design phase only. No implementation, no trading logic.**
Builds on `docs/ARCHITECTURE.md` (core engine design). This document goes
deeper on two subsystems: the CoinGlass Data Layer and the Strategy
Framework/Plugin system. No strategy rules are assumed or invented anywhere
below — only the interfaces and pipeline that will host your proprietary
logic.

---

## 1. CoinGlass Data Layer Architecture

The data layer is internally layered so that each concern (auth, rate
limiting, retries, validation, storage) is a separate, replaceable piece.
The Strategy Engine and Core Engine never see any of these internals or
anything CoinGlass-shaped — they only ever see canonical schema objects
served through the repository/handler.

```
CoinGlass API
     │
     ▼
┌─────────────────────────┐
│ CoinGlassClient          │  auth headers, base URL, endpoint methods
│  ├─ AuthProvider          │  API key injection (env/config, rotation-ready)
│  ├─ RateLimiter           │  per-endpoint token bucket / sliding window
│  └─ RetryPolicy           │  exponential backoff + jitter; retryable
│                           │  (429/5xx/timeout) vs. fatal (4xx auth/bad req)
└───────────┬──────────────┘
            │ raw JSON
            ▼
┌─────────────────────────┐
│ ResponseValidator         │  schema-checks raw payload; fails fast on
└───────────┬──────────────┘  malformed data or upstream contract changes
            │ validated raw JSON
            ▼
┌─────────────────────────┐
│ CoinGlassDataProvider     │  Adapter: raw → canonical schema
│  (implements              │  (Bar, FundingRate, OpenInterest,
│   MarketDataProvider ABC) │   Liquidation, LongShortRatio, ...)
└───────────┬──────────────┘
            │ canonical models
            ▼
┌─────────────────────────┐
│ DataRepository             │  Parquet + DuckDB local cache;
│                            │  range/symbol queries; cache-first reads
└───────────┬──────────────┘
            │
            ▼
┌─────────────────────────┐
│ DataSyncService            │  Facade: "give me symbol X, range Y" →
│  (gap detection +          │  checks cache, fetches only missing gaps
│   fetch orchestration)     │  from the provider, validates, stores
└───────────┬──────────────┘
            │
            ▼
┌─────────────────────────┐
│ DataHandler                 │  Streams canonical data chronologically to
│  (time-bounded access)      │  the Core Engine as MarketEvents; enforces
│                              │  "no data beyond current sim time" to
└─────────────────────────┘  prevent lookahead bias
```

### Responsibilities per component

- **CoinGlassClient** — the only piece of code in the whole system that
  knows CoinGlass's URLs, headers, and endpoint parameters. Pure transport.
- **AuthProvider** — resolves the API key from config/environment; kept
  separate so key rotation or a future auth scheme change touches one file.
- **RateLimiter** — configurable per endpoint (CoinGlass's futures OHLC,
  funding rate, open interest, liquidation, and long/short-ratio endpoints
  will typically have different limits/tiers). Implemented as a pluggable
  strategy so it can be swapped for a smarter distributed limiter later.
- **RetryPolicy** — distinguishes transient failures (retry with backoff)
  from permanent ones (fail immediately: bad API key, malformed request).
- **ResponseValidator** — validates the *raw* response shape before it's
  trusted, so a CoinGlass API change is caught here with a clear error,
  not as a silent data-corruption bug three layers downstream.
- **CoinGlassDataProvider** — the Adapter. Implements the generic
  `MarketDataProvider` interface (`get_ohlcv`, `get_funding_rate`,
  `get_open_interest`, `get_liquidations`, `get_long_short_ratio`, all
  returning canonical pydantic models). This is the *only* class that
  bridges "CoinGlass" and "the engine's world."
- **DataRepository** — local persistence (Parquet files + DuckDB for
  querying them). Owns the cache-hit/cache-miss decision for a given
  symbol/timeframe/date range.
- **DataSyncService** — the practical entry point used by the CLI/backtest
  setup step: "ensure I have data for BTC 1h Jan–Jun 2024" → computes what's
  missing, calls the provider only for the gaps, validates, writes to the
  repository. This is what makes backtests reproducible offline after the
  first fetch.
- **DataHandler** — the sole connection point into the Core Engine. Reads
  from the repository (never the provider directly) and emits
  `MarketEvent`s in chronological order, bounded by the simulation clock.

### Provider independence

`MarketDataProvider` is the only contract the rest of the system depends
on. Swapping CoinGlass for another provider later means writing one new
adapter class (`BinanceDataProvider`, etc.) that returns the same canonical
models — zero changes to `DataRepository`, `DataHandler`, the Core Engine,
or the Strategy Engine. Which provider is active is a config/composition-root
decision, never a code branch inside shared modules.

### Design patterns used here

- **Adapter** — `CoinGlassDataProvider` (raw API → canonical schema).
- **Facade** — `DataSyncService` gives callers one simple method instead of
  requiring them to orchestrate client/validator/repository themselves.
- **Repository** — `DataRepository` isolates storage/query mechanics.
- **Decorator/Chain** — rate limiting, retry, and logging wrap the raw
  client calls as composable layers rather than being hardcoded inline.
- **Strategy pattern** (generic sense, not trading) — `RateLimiter` and
  `RetryPolicy` are themselves swappable implementations behind small
  interfaces.

---

## 2. Strategy Engine Architecture

### Hard boundary

The Backtesting Engine defines **only abstract interfaces** for strategy
components. It never contains an implementation of any of them. Your
proprietary logic lives entirely in a separate plugin package (see §3) that
the engine loads by name at runtime and never inspects further.

### Sub-component interfaces

Each of the pieces you listed becomes its own independent interface —
not methods on one giant `Strategy` class. This is what "every strategy
component remains independent" means structurally: each one can be
developed, tested, and replaced without touching the others.

| Interface | Consumes | Produces | Corresponds to |
|---|---|---|---|
| `MarketAnalyzer` (one per analysis type) | `StrategyContext` (time-bounded market data view) | `AnalysisResult` | Funding Rate Analysis, Open Interest Analysis, Premium/Discount Analysis, Liquidity Analysis |
| `ScoringModel` | `list[AnalysisResult]` | `Score` | Your proprietary Scoring Model |
| `NoTradeConditionCheck` (chainable, one or many) | `Score`, `StrategyContext` | `bool` (blocked) + reason | No Trade Conditions |
| `RiskManagementPolicy` (strategy-level) | `Score`, `StrategyContext`, read-only portfolio snapshot | risk-adjusted trade parameters (size/leverage constraints) | Risk Management Rules |
| `PositionManagementPolicy` | `Score`, current position state | position sizing/scaling decisions | Position Management Rules |
| `TradeManagementPolicy` | open position state, `StrategyContext` | in-trade adjustments (stop moves, partial exits) | Trade Management Rules |
| `ExitPolicy` | open position state, `StrategyContext` | exit decision | Exit Rules |

Note on **Risk Management Rules**: the Core Engine already has a generic,
strategy-agnostic `risk/` module (position limits, max-drawdown circuit
breakers — applies to *any* strategy as a safety net). Your strategy's own
`RiskManagementPolicy` is separate and proprietary (e.g., strategy-specific
sizing logic informed by the Score). Both exist; they operate at different
levels and neither depends on the other.

### The orchestrating `Strategy` interface

The engine only ever talks to one method-level contract:

```
Strategy.on_market_event(context: StrategyContext) -> list[SignalEvent]
```

Everything above — analyzers, scoring, no-trade checks, risk/position/
trade-management/exit policies — is composed *inside* the concrete
implementation of this method, inside your plugin package. The engine
never imports, calls, or reflects into any of those internal pieces. This
single-method boundary is the actual mechanism that keeps proprietary logic
opaque to the engine (and to anyone who only has access to the engine
repo).

Internally, the plugin's `Strategy` implementation follows a fixed pipeline
(Template Method), but the *shape* of the pipeline is architecture, not
logic:

1. Run registered `MarketAnalyzer`s → collect `AnalysisResult`s.
2. Pass results to `ScoringModel` → get a `Score`.
3. Evaluate `NoTradeConditionCheck`s against the `Score` — if any blocks,
   stop here for this event.
4. If no position is open: apply `RiskManagementPolicy` +
   `PositionManagementPolicy` to size a potential entry → emit an entry
   `SignalEvent` (or none).
5. If a position is open: apply `TradeManagementPolicy` and `ExitPolicy` →
   emit adjustment/exit `SignalEvent`s (or none).

### `StrategyContext` — the data-access boundary

`StrategyContext` is what analyzers and policies actually read from. It
wraps:
- The current canonical bar/tick.
- Bounded historical lookback access into the `DataRepository` (funding
  rate history, OI history, liquidations, long/short ratio, price history)
  — bounded by the engine's current simulation clock so a strategy
  component can never read future data (look-ahead bias prevention is
  enforced structurally here, not by convention).
- A read-only snapshot of portfolio/position state.

No analyzer or policy ever talks to the `DataRepository`, `DataHandler`, or
`Portfolio` directly — only through `StrategyContext`. That keeps every
strategy component testable in isolation with a fabricated context.

---

## 3. Plugin Architecture

### Where proprietary code lives

**Recommendation: the strategy is a separate, independently-installable
Python package in its own (private) repository — not a folder inside
`backtesting-engine`.** The engine repository depends on nothing from the
strategy; the strategy package depends on the engine (`btengine`) as a
library. This means the engine repo could be shared, reviewed by a
contractor, or even open-sourced later without ever exposing your scoring
model or rules, because they never live in this repo at all.

### Discovery mechanism

- The plugin declares an **entry point** in its own `pyproject.toml` under
  a dedicated group, e.g. `btengine.strategies`, pointing at its concrete
  `Strategy` subclass.
- The engine's `StrategyRegistry` calls
  `importlib.metadata.entry_points(group="btengine.strategies")` at
  startup to discover whatever strategy packages happen to be installed in
  the environment, and instantiates the one selected by config (by name).
- **The engine source code never references your plugin's package or
  module path.** Nothing to grep for, nothing to import statically.

### Internal shape of the plugin package (example, structure only)

```
my-proprietary-strategy/            (separate private repo)
├── pyproject.toml                  # declares entry point under "btengine.strategies"
├── src/my_strategy/
│   ├── strategy.py                 # concrete Strategy: composes everything below
│   ├── analyzers/
│   │   ├── funding_rate.py
│   │   ├── open_interest.py
│   │   ├── premium_discount.py
│   │   └── liquidity.py
│   ├── scoring/
│   │   └── model.py                 # proprietary scoring logic
│   ├── risk/
│   │   └── rules.py
│   ├── no_trade/
│   │   └── conditions.py
│   ├── trade_management/
│   │   └── rules.py
│   ├── position_management/
│   │   └── rules.py
│   ├── exit/
│   │   └── rules.py
│   └── config/
│       └── parameters.yaml          # thresholds/weights — kept out of the engine repo entirely
└── tests/
```

### Config, not hardcoding

Tunable parameters (thresholds, weights, lookback windows) live in the
plugin's own config, validated by a pydantic schema the plugin defines.
The engine passes a config path/dict through opaquely — it never inspects
or depends on the contents. This also sets up parameter sweeps/optimization
later without code changes (just generate config variants).

### Versioning

Every backtest result should record the strategy plugin's package version
alongside the engine version and data snapshot used — a prerequisite for
reproducibility once you're iterating on the scoring model over time.

---

## 4. Module Communication Flow

```
DataSyncService (pre-run)
        │  populates local cache from CoinGlass
        ▼
DataHandler ──MarketEvent──▶ Core Engine Event Queue
        ▲                         │
        │ time-bounded queries    │ dispatch
        │                         ▼
        │                 Strategy Plugin instance
        │                         │
        │        ┌────────────────┴────────────────┐
        │        │   internal pipeline (opaque to    │
        │        │   engine, lives in plugin repo):  │
        │        │                                    │
        │        │   MarketAnalyzers → AnalysisResults│
        │        │        → ScoringModel → Score      │
        │        │        → NoTradeConditionChecks     │
        │        │        → Risk/Position Mgmt (entry) │
        │        │          or Trade Mgmt/Exit (open)  │
        │        └────────────────┬────────────────┘
        │                         │ SignalEvent(s) (0..n)
        └─────(StrategyContext queries data repo, read-only, time-bounded)
                                  ▼
                        Engine Risk Manager (generic,
                        strategy-agnostic safety net)
                                  │ OrderEvent
                                  ▼
                        Execution Handler (simulated fills)
                                  │ FillEvent
                                  ▼
                              Portfolio
                                  │
                                  ▼
                        Analytics & Reporting
```

Key point: the arrow from `Core Engine` into `Strategy Plugin` crosses the
proprietary boundary carrying only a `StrategyContext` object; the arrow
back carries only `SignalEvent`s. Nothing about *how* the plugin decided
crosses that boundary — by construction, not by convention.

---

## 5. Data Flow Diagram (CoinGlass → Portfolio)

```
CoinGlass API
   │ HTTPS
   ▼
CoinGlassClient (auth + rate limit + retry)
   │ raw JSON
   ▼
ResponseValidator
   │ validated raw JSON
   ▼
CoinGlassDataProvider (Adapter → canonical schema)
   │ canonical models: Bar / FundingRate / OpenInterest / Liquidation / LongShortRatio
   ▼
DataRepository (Parquet + DuckDB cache)
   │ range/symbol query results
   ▼
DataSyncService (gap-fill orchestration, run once before/at start of backtest)
   ▼
DataHandler (chronological, time-bounded streaming)
   │ MarketEvent
   ▼
Core Engine Event Queue
   │ dispatch
   ▼
Strategy Plugin
   (Analyzers → Scoring → No-Trade → Risk/Position/Trade-Mgmt/Exit)
   │ SignalEvent
   ▼
Engine Risk Manager (generic pre-trade checks)
   │ OrderEvent
   ▼
Execution Handler (simulated fills, fees, slippage, funding cost)
   │ FillEvent
   ▼
Portfolio / Position Manager
   │ recorded equity curve + trade log
   ▼
Analytics & Reporting
```

---

## 6. Recommended Folder Structure

### Engine repo (`backtesting-engine`) — interfaces only, no strategy logic

```
backtesting-engine/
└── src/btengine/
    ├── data/
    │   ├── base.py                   # MarketDataProvider ABC
    │   ├── schema.py                 # canonical models
    │   ├── validation.py             # raw + canonical validators
    │   ├── repository.py             # Parquet/DuckDB cache + queries
    │   ├── sync.py                   # DataSyncService (gap detection/fetch)
    │   ├── handler.py                # DataHandler (time-bounded streaming)
    │   └── providers/
    │       └── coinglass/
    │           ├── client.py         # CoinGlassClient (HTTP transport)
    │           ├── auth.py           # AuthProvider
    │           ├── rate_limiter.py   # per-endpoint limits
    │           ├── mapper.py         # raw → canonical translation
    │           └── provider.py       # CoinGlassDataProvider (implements MarketDataProvider)
    └── strategy/
        ├── base.py                   # Strategy ABC (on_market_event only)
        ├── context.py                # StrategyContext (time-bounded, read-only)
        ├── registry.py                # entry-point based StrategyRegistry
        ├── analyzers/
        │   └── base.py                # MarketAnalyzer ABC, AnalysisResult type
        ├── scoring/
        │   └── base.py                # ScoringModel ABC, Score type
        ├── no_trade/
        │   └── base.py                # NoTradeConditionCheck ABC
        ├── risk/
        │   └── base.py                # RiskManagementPolicy ABC (strategy-level)
        ├── position_management/
        │   └── base.py                # PositionManagementPolicy ABC
        ├── trade_management/
        │   └── base.py                # TradeManagementPolicy ABC
        └── exit/
            └── base.py                # ExitPolicy ABC
```

### Strategy plugin repo — **separate, private, not part of this repo**

```
my-proprietary-strategy/              # example name — a different git repo entirely
├── pyproject.toml                    # entry point: btengine.strategies -> strategy.py:MyStrategy
└── src/my_strategy/
    ├── strategy.py
    ├── analyzers/ ...
    ├── scoring/ ...
    ├── risk/ ...
    ├── no_trade/ ...
    ├── trade_management/ ...
    ├── position_management/ ...
    ├── exit/ ...
    └── config/parameters.yaml
```

---

## 7. Future Scalability Recommendations

- **Parallel analyzers** — if analyzers become computationally heavy
  (e.g., deep liquidity/order-book analysis), the `MarketAnalyzer` interface
  should support async/thread-pool execution without changing its contract.
- **Intermediate result caching** — analyzers keyed on data that updates
  less frequently than every bar (e.g., OI trend on an hourly cadence)
  should memoize by `(symbol, timeframe, timestamp)` rather than
  recomputing every tick.
- **Versioned scoring models** — since `ScoringModel` is an interface, you
  can run multiple versions side-by-side against identical historical data
  for research/A-B comparison without touching the engine.
- **Parameter sweeps** — because plugin parameters are a validated config
  object, grid-search/walk-forward optimization is "generate many config
  files, run many backtests," not a code change.
- **New CoinGlass endpoints** — adding a new metric only means a new
  mapper function and a new canonical schema field; no engine or strategy
  interface changes, because the Adapter boundary already absorbs this.
- **Provider failover** — a circuit breaker plus an optional secondary
  provider could be added at the `MarketDataProvider` factory level later
  (e.g., if CoinGlass has an outage) with zero changes above that layer.
- **Multi-strategy portfolios** — running several strategy plugins against
  a shared portfolio is a future extension: a `StrategyEnsemble` that
  itself implements the `Strategy` ABC and internally fans out to several
  plugins — transparent to the Core Engine, not needed now.
- **Live/Demo Agent reuse** — analyzers, scoring, no-trade, risk,
  trade-management, position-management, and exit policies depend only on
  `StrategyContext`, never on "this is a backtest." The same plugin package
  runs unmodified later under a live `StrategyContext` implementation
  backed by real-time data instead of historical replay.

---

**Awaiting your approval before implementing any part of this — data
layer, strategy interfaces, or plugin scaffolding.**
