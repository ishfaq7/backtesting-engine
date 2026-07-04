# Backtesting Engine — Architecture Design

Status: **Design phase only. No implementation code has been written.**
Scope: This document covers the Backtesting Engine exclusively. All other
platform components (Strategy runtime beyond backtesting, Demo/Live/Hedge
Trading Agents, AI Analysis Agent, Web Dashboard, multi-user SaaS layer) are
explicitly out of scope for this phase, but the design below is written so
those components can later be built *on top of* this engine without
rewriting it.

---

## 1. Guiding Principles

1. **The engine is a library, not an application.** It has no GUI, no web
   server, no CLI logic baked into its core — those are thin shells around a
   pure Python API.
2. **Event-driven core.** Data → Strategy → Risk → Portfolio → Execution
   communicate exclusively through typed events on a queue, never through
   direct method calls into each other's internals. This is what lets the
   same core loop later run in "live" mode by swapping two components
   (data source, execution handler) instead of rewriting the engine.
3. **Strategy logic is a plugin, not a dependency.** Strategies depend only
   on abstract interfaces (`Strategy`, `StrategyContext`). The engine never
   imports a concrete strategy; it discovers and loads them.
4. **Provider independence.** CoinGlass is the first data source, not the
   only one. Every CoinGlass-specific detail lives behind an `Adapter`
   interface, so a Binance/Bybit adapter can be added later without
   touching the engine.
5. **No hidden global state.** No singletons holding user/session state.
   This is what makes multi-tenancy retrofit-able later instead of a
   rewrite.

---

## 2. Module Map & Responsibilities

```
                          ┌─────────────────────┐
                          │   Config Module      │  (loads + validates settings)
                          └──────────┬───────────┘
                                     │ injects config
                                     ▼
┌────────────┐   raw data   ┌───────────────┐   canonical bars   ┌────────────────┐
│ Data        │─────────────▶│ Data           │───────────────────▶│ Data Handler    │
│ Provider    │              │ Repository /   │                     │ (feeds engine)  │
│ (CoinGlass  │              │ Cache          │                     └────────┬────────┘
│  Adapter)   │              └───────────────┘                              │ MarketEvent
└────────────┘                                                              ▼
                                                                    ┌─────────────────┐
                                                                    │   EVENT QUEUE    │◀────────────┐
                                                                    │  (core engine)   │             │
                                                                    └───┬───────┬──────┘             │
                                                     MarketEvent ───────┘       │                    │
                                                                                ▼                    │
                                                                    ┌─────────────────┐              │
                                                                    │ Strategy Plugin  │  SignalEvent │
                                                                    │ (via Registry)   │──────────────┤
                                                                    └─────────────────┘              │
                                                                                                       │
                                                                    ┌─────────────────┐  OrderEvent   │
                                                                    │ Risk Manager     │───────────────┤
                                                                    └─────────────────┘               │
                                                                                                        │
                                                                    ┌─────────────────┐   FillEvent    │
                                                                    │ Execution Handler│────────────────┘
                                                                    │ (Simulated)      │
                                                                    └────────┬────────┘
                                                                             ▼
                                                                    ┌─────────────────┐
                                                                    │ Portfolio /      │
                                                                    │ Position Manager │
                                                                    └────────┬────────┘
                                                                             ▼
                                                                    ┌─────────────────┐
                                                                    │ Analytics &      │
                                                                    │ Reporting        │
                                                                    └─────────────────┘
```

### 2.1 Config Module
Loads and validates all runtime configuration: API credentials, backtest
date ranges, symbols, timeframes, fee/slippage models, strategy parameters,
risk limits. Single source of truth injected into every other module at
startup (composition root) — nothing reads config from globals.

### 2.2 Data Provider (CoinGlass Adapter)
Talks to the CoinGlass API. Responsible for: authenticated HTTP calls,
pagination, rate-limit handling, retries/backoff, and translating
CoinGlass's response shape into the engine's **canonical data schema**
(OHLCV bars, funding rates, open interest, long/short ratios, liquidations).
This is the *only* module that knows CoinGlass exists. Implements a generic
`MarketDataProvider` interface so a future provider (Binance, Bybit, on-chain
data) is a drop-in replacement.

### 2.3 Data Repository / Cache
Persists fetched data locally (so backtests are reproducible and don't
re-hit the API) and serves range/symbol queries efficiently. Decouples
"fetching" from "reading during a run" — a backtest never talks to
CoinGlass directly, it reads from the repository.

### 2.4 Data Handler
The component the core engine actually talks to. Streams canonical bars in
chronological order and emits `MarketEvent`s onto the queue. In live/demo
mode, this component is replaced by a streaming handler (websocket feed)
that emits the same `MarketEvent` type — this is the seam that makes engine
reuse possible.

### 2.5 Core Engine (Event Loop / Orchestrator)
Owns the event queue and the run loop: pop an event, route it to the
component that consumes that event type, push whatever event it produces,
repeat until the data handler signals "no more data." Contains no trading
logic itself — it's a scheduler/mediator.

### 2.6 Strategy Plugin System
Defines the `Strategy` abstract interface and a `StrategyContext` (read-only
snapshot of current bar, indicator values, portfolio state) passed into it.
A `StrategyRegistry` discovers installed strategy plugins (via Python
entry points or a plugins directory) and instantiates the one selected by
config. Strategies emit `SignalEvent`s only — they never touch the
portfolio, execution, or data layers directly. This isolation is what
"strategy logic completely separate from the engine" means concretely.

### 2.7 Indicator Library
Shared, reusable technical indicators available to any strategy
(moving averages, RSI, ATR, etc.), plus an interface for strategies to
register custom indicators. Kept separate from strategy logic so
indicators are reusable across many strategies.

### 2.8 Risk Manager
Consumes `SignalEvent`s, applies pre-trade rules (position sizing, max
exposure, max leverage, stop-loss/take-profit policy), and converts
approved signals into `OrderEvent`s. Pluggable rule set, independent of any
specific strategy.

### 2.9 Execution Handler (Simulated Broker)
Consumes `OrderEvent`s and simulates fills: applies slippage and fee
models, models funding-rate cost for perpetuals, and emits `FillEvent`s.
Implements an `ExecutionHandler` interface that a Live Trading Agent will
later implement against a real exchange connection — same interface,
different backend.

### 2.10 Portfolio / Position Manager
Consumes `FillEvent`s and is the single source of truth for cash, open
positions, margin usage, and realized/unrealized PnL. Pure state + math,
no I/O, easily unit-testable and reusable unchanged by live/demo agents.

### 2.11 Analytics & Reporting
Reads the portfolio's recorded equity curve and trade log *after* (or
incrementally during) a run and computes performance metrics (Sharpe,
Sortino, max drawdown, win rate, CAGR, profit factor, exposure, etc.).
Outputs serializable result objects — files or in-memory records — with no
knowledge of how they'll be displayed (GUI, dashboard, or terminal print are
all downstream concerns).

### 2.12 Plugin Registry (cross-cutting)
A generic discovery/registration mechanism reused by the Strategy,
Indicator, Data Provider, and Execution Handler modules, so adding any new
implementation of any of these is "drop a package in, register an entry
point" rather than editing engine code.

### 2.13 CLI (thin shell, not core)
A command-line entry point that loads config, wires up the concrete
components via the composition root, and runs a backtest. Contains no
business logic — everything it does is available through the same Python
API a future web backend will call.

---

## 3. Inter-Module Communication

- **Primary channel: the event queue.** `MarketEvent → SignalEvent →
  OrderEvent → FillEvent`. Every module only knows the event types it
  consumes and produces — never the internals of the module up- or
  downstream. This is a **Mediator/Pub-Sub** pattern in effect, even though
  implemented as a simple queue rather than a message broker.
- **Composition root wiring:** the Config module and a top-level factory
  assemble concrete instances (which `DataProvider`, which `Strategy`,
  which `ExecutionHandler`) once at startup and inject them into the Core
  Engine — no module resorts to a global registry lookup at runtime except
  the plugin discovery step itself.
- **Read-only side channels:** Analytics reads Portfolio's recorded history
  after the fact; it does not participate in the event loop and cannot feed
  anything back into it.
- **No direct imports across strategy/engine boundary:** strategies import
  only `btengine.strategy.base` and `btengine.indicators`; they never import
  `btengine.core`, `btengine.execution`, or `btengine.data` internals.

---

## 4. Module Dependency Graph

```
config            → (no dependencies; pydantic models only)
data.providers.*  → data.base, data.schema, config
data.repository   → data.schema
data.handler      → data.repository, core.events
strategy.base     → core.events (Signal types only), indicators (optional)
strategy.registry → strategy.base, plugins.loader
indicators        → (no engine dependency; pure functions over price series)
risk              → core.events, portfolio (read-only), config
execution.base    → core.events
execution.simulated → execution.base, portfolio (read-only), config (fees/slippage)
portfolio         → core.events (consumes FillEvent only)
analytics         → portfolio (read-only), no dependency back into core loop
core.engine       → data.handler, strategy.registry, risk, execution.base, portfolio
cli               → config, core.engine (composition root only)
```

Key property: **strategy plugins sit at the edge of the graph** — they
depend only on abstract interfaces, never on the engine or on concrete
execution/data implementations. This is exactly the property that lets
Demo and Live Trading Agents reuse `strategy/`, `indicators/`, `portfolio/`,
`risk/`, and `analytics/` almost unchanged, swapping only `data/` (live feed
instead of historical) and `execution/` (real broker instead of simulator).

---

## 5. Proposed Folder Structure

```
backtesting-engine/
├── pyproject.toml
├── README.md
├── docs/
│   └── architecture.md
├── config/
│   ├── engine.yaml
│   └── strategies/
│       └── example_strategy.yaml
├── src/
│   └── btengine/
│       ├── __init__.py
│       ├── api.py                  # public facade: run_backtest(config) -> BacktestResult
│       ├── core/
│       │   ├── engine.py           # BacktestEngine orchestrator (event loop)
│       │   ├── events.py           # MarketEvent, SignalEvent, OrderEvent, FillEvent
│       │   └── event_queue.py
│       ├── data/
│       │   ├── base.py             # MarketDataProvider ABC
│       │   ├── schema.py           # canonical pydantic models (Bar, FundingRate, OI, ...)
│       │   ├── providers/
│       │   │   └── coinglass.py    # CoinGlassDataProvider (adapter)
│       │   ├── repository.py       # local cache/query layer (Parquet/DuckDB)
│       │   └── handler.py          # DataHandler feeding MarketEvents to engine
│       ├── strategy/
│       │   ├── base.py             # Strategy ABC
│       │   ├── context.py          # StrategyContext passed into strategies
│       │   └── registry.py         # plugin discovery/registration
│       ├── indicators/
│       │   ├── base.py
│       │   └── library/            # built-in indicators
│       ├── risk/
│       │   ├── base.py
│       │   └── rules/              # pluggable pre-trade risk rules
│       ├── execution/
│       │   ├── base.py             # ExecutionHandler ABC
│       │   ├── simulated.py        # SimulatedExecutionHandler
│       │   └── models.py           # fee / slippage / funding models
│       ├── portfolio/
│       │   ├── portfolio.py
│       │   └── position.py
│       ├── analytics/
│       │   ├── metrics.py          # Sharpe, Sortino, drawdown, CAGR, ...
│       │   └── reporting.py        # serializable result objects, export
│       ├── config/
│       │   ├── loader.py
│       │   └── models.py           # pydantic-settings models
│       ├── plugins/
│       │   └── loader.py           # generic entry-point/plugin discovery
│       ├── utils/
│       │   ├── logging.py
│       │   └── time.py
│       └── cli/
│           └── main.py             # Typer entry point (thin shell over api.py)
├── strategies/                     # user-contributed strategy plugins (external)
│   └── example_ma_crossover/
│       ├── strategy.py
│       └── plugin.toml
├── data_cache/                     # local historical data cache (gitignored)
├── tests/
│   ├── unit/
│   └── integration/
└── scripts/
    └── run_backtest.py
```

`src/` layout is used deliberately (not a flat package at repo root) so the
package installs cleanly and is importable by future sibling projects
(Demo Agent, Live Agent) as a normal dependency (`pip install -e
../backtesting-engine` or a private package index) without path hacks.

---

## 6. Recommended Design Patterns

| Pattern | Where | Why |
|---|---|---|
| **Adapter** | `data/providers/coinglass.py` | Isolates CoinGlass's API shape from the engine's canonical schema; future providers plug in the same way. |
| **Strategy** | `strategy/` | Textbook fit — interchangeable trading logic behind one interface. |
| **Event-driven / Mediator** | `core/engine.py` + `core/events.py` | Decouples every stage of the pipeline; the seam that enables live-trading reuse. |
| **Repository** | `data/repository.py` | Separates "where data comes from" from "how it's queried/stored." |
| **Factory / Composition Root** | top-level wiring in `api.py` / `cli/main.py` | Builds concrete `DataProvider`/`ExecutionHandler`/`Strategy` instances from config; single place that knows concrete types. |
| **Template Method** | `core/engine.py` run loop | Fixed skeleton (fetch → signal → risk → execute → record) with pluggable steps. |
| **Command** | `OrderEvent` | Orders as inert data objects executed by the handler, not behavior baked into the strategy. |
| **Plugin Registry (via entry points)** | `plugins/loader.py`, `strategy/registry.py` | Extensibility without modifying engine source — critical for "plugin-based strategies." |
| **Dependency Injection** | throughout, via composition root | No module reaches out to a global for its collaborators; everything is passed in — required for parallel backtests and later multi-tenancy. |

Avoid: Singleton for anything holding run-specific or user-specific state
(config, portfolio, logger context) — it blocks parallel backtests and
multi-tenant reuse later. A shared logger *instance* is fine; shared
*mutable trading state* is not.

---

## 7. Recommended Python Libraries

| Concern | Recommendation | Notes |
|---|---|---|
| HTTP client (CoinGlass) | `httpx` | Async-capable, modern; pair with `tenacity` for retry/backoff. |
| Rate limiting | `aiolimiter` (or a small token-bucket) | CoinGlass tiers have request limits. |
| Data manipulation | `pandas` (default), consider `polars` later | Start with pandas for ecosystem compatibility; revisit if multi-year/multi-symbol datasets get memory-heavy. |
| Schema/validation | `pydantic` v2 | Canonical data models, config models, result objects — also gives free JSON serialization for future API use. |
| Local storage/cache | `pyarrow` (Parquet) + `duckdb` for queries | Fast columnar storage, cheap analytical queries over cached history without a DB server. |
| Config files | `pydantic-settings` + `PyYAML` | Typed, validated config with env-var override support. |
| CLI | `Typer` | Thin, typed CLI wrapping the public API. |
| Plugin discovery | `importlib.metadata` entry points | Standard, no custom magic; strategies register via their own `pyproject.toml`. |
| Indicators | `pandas-ta` | Pure Python, avoids TA-Lib's C-extension install friction. |
| Logging | `structlog` | Structured logs pay off once this feeds live-trading observability. |
| Performance metrics | `empyrical-reloaded` (maintained fork) or thin custom wrappers | Sharpe/Sortino/drawdown/CAGR without reinventing the math. |
| Testing | `pytest`, `pytest-cov`, `hypothesis` | Property-based tests are especially valuable for portfolio/PnL math correctness. |
| Packaging/env | `uv` (or Poetry) | Fast, modern dependency management; `src/` layout plays well with either. |
| Parallel backtests (later) | `multiprocessing` → `Ray`/`Dask` if needed | Only once parameter-sweep/optimization workloads justify it. |

---

## 8. Future Scalability Challenges (to anticipate, not solve now)

1. **Memory pressure** from multi-year, multi-symbol, fine-grained
   historical data in pandas — may require Polars/DuckDB or chunked
   streaming reads instead of loading full history into memory.
2. **Parallel/batch backtests** (parameter sweeps, walk-forward
   optimization) require each engine run to be a fresh, isolated instance
   with no shared mutable state — the DI-based design above is what makes
   this tractable later via `multiprocessing`/Ray.
3. **CoinGlass rate limits** — aggressive caching and backoff are required
   from day one; a thin client wrapper isn't enough on its own.
4. **Execution realism drift** — simulated fills (slippage/fee/funding
   models) diverging from real exchange behavior is the single biggest
   risk when this engine's components get reused for live trading; the
   `ExecutionHandler` interface needs to support increasingly realistic
   models over time (latency, partial fills, order book depth).
5. **Reproducibility/versioning** — pinning the exact data snapshot,
   strategy version, and config used for a given run becomes important
   once results are compared across iterations or, later, across users.
6. **Observability** — structured logging now pays off later when the same
   core loop runs unattended in a live agent and needs metrics/alerting
   (Prometheus/Grafana-style integration).
7. **Timezone/time-alignment correctness** across data sources — a subtle,
   easy-to-get-wrong source of invalid backtests as more data types
   (funding rates, OI, liquidations) with different update cadences are
   combined.

---

## 9. Preparing for Future Web Integration

- Keep a single **public API facade** (`btengine.api`) exposing functions
  like `run_backtest(config) -> BacktestResult` — this is exactly what a
  future FastAPI backend will import and call; the CLI already goes through
  this same facade, so there's no second code path to keep in sync.
- All results (`BacktestResult`, trade logs, equity curves) are **pydantic
  models**, which serialize to JSON for free — a REST layer can return them
  with zero translation code.
- Design the run loop to optionally accept a **progress callback/event
  hook** (e.g., "bar N of M processed") so a future API server can stream
  progress over a WebSocket without changes to the engine itself — just an
  additional subscriber on the existing event mechanism.
- Long-running backtests should be structured so they *can* run as
  background jobs (no engine-internal assumption that it must run
  synchronously in the calling process) — this anticipates a task
  queue (Celery/RQ/arq) sitting in front of the engine later.

---

## 10. Preparing for Multi-User SaaS

- **No global mutable state anywhere in the engine** (already a core
  principle above) — this is the single most important prerequisite;
  retrofitting tenancy onto code with global state is a rewrite, not a
  patch.
- **Separate shared data from user-owned data at the storage layer now**,
  even while both are just local files: market data cache (shared,
  provider-sourced) vs. user strategies/configs/results (owned). This
  mirrors the eventual split of "shared market data cache" vs. "per-tenant
  Postgres rows + S3 objects."
- **Namespace the plugin registry** by owner (`tenant_id/strategy_name`)
  from the start, even with a single flat local registry today — cheap
  now, expensive to bolt on once strategies are stored per-user.
- **Config is already tenant-shaped** via pydantic-settings — resolving
  "which config for which user" later is a lookup change, not an
  architecture change.
- **Job isolation**: design each backtest invocation to be a self-contained
  unit of work (one process/container per run is the eventual target) so
  a single user's strategy bug or runaway loop can't affect others — a
  natural fit once a task queue + worker pool is introduced.
- **Resource quotas** (max run duration, concurrent run limits) aren't
  needed today, but the composition root is the natural place to insert
  a quota check later — flag it as a known extension point, don't build
  it now.

---

## 11. Milestone-Based Development Plan

| # | Milestone | Deliverable |
|---|---|---|
| 0 | **Project scaffolding** | Repo layout, `pyproject.toml`, `src/` package skeleton, linting/formatting (`ruff`, `mypy`), `pytest` wired into CI. |
| 1 | **Core domain models & events** | `core/events.py` event types, canonical `data/schema.py` models (Bar, FundingRate, OpenInterest, ...), config loader/models. |
| 2 | **Data layer** | `MarketDataProvider` ABC, `CoinGlassDataProvider` (fetch, rate-limit, retry), local Parquet/DuckDB repository, `DataHandler` that streams `MarketEvent`s. |
| 3 | **Portfolio & execution** | `Portfolio`/`Position` state tracking, `SimulatedExecutionHandler` with fee/slippage/funding models, basic order types. |
| 4 | **Strategy plugin system** | `Strategy` ABC, `StrategyContext`, entry-point-based `StrategyRegistry`, one reference "smoke test" strategy used only to validate the interface (not real strategy logic — out of scope). |
| 5 | **Core engine loop** | `BacktestEngine` wiring Data → Strategy → Risk → Portfolio → Execution through the event queue; first end-to-end single-run backtest. |
| 6 | **Risk management module** | Pluggable pre-trade rules: position sizing, max exposure/leverage, stop-loss/take-profit hooks. |
| 7 | **Analytics & reporting** | Sharpe/Sortino/drawdown/CAGR/profit-factor metrics, trade log export, serializable `BacktestResult`. |
| 8 | **CLI interface** | Typer CLI that loads config and runs a full backtest via the public `btengine.api` facade. |
| 9 | **Testing & validation** | Unit tests per module, integration test with a stub/mock data provider, property-based tests for portfolio/PnL math. |
| 10 | **Hardening for reuse** | Finalize `btengine.api` public facade, docs, a parallel/batch backtest runner (multiprocessing) for parameter sweeps — the direct precursor to Demo/Live Agent integration and future web/SaaS work. |

**Awaiting your approval before starting Milestone 0 / any implementation.**
