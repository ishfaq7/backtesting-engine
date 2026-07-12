# Feature Engineering & Analysis Layer

Status: **Transformation only. No trading strategy, signal, or scoring
logic has been implemented.** This layer converts raw CoinGlass market
data (already validated into the canonical schema by the Data Layer)
into standardized, named analytical features. It has no concept of BUY,
SELL, "good"/"bad", or a threshold that would trigger a decision — those
belong entirely to the (not-yet-implemented) proprietary strategy layer,
which will consume this layer's output as an input, never the reverse.

Three of the eight required modules — Premium/Discount, Market Structure,
CVD — are **framework-only placeholders**: their inputs aren't available
yet (no paired spot-price series, no strategy-defined structure
definition, no taker buy/sell volume split), so `compute()` raises
`NotImplementedError` rather than guessing at a formula.

## 1. Folder structure

```
src/btengine/features/
├── base.py                        (existing) FeatureValue, FeatureAnalyzer, HistoricalCandleSource
├── multi_timeframe.py              (existing, untouched)
├── atr.py, cvd.py, market_structure.py   (existing single-point-in-time stubs, untouched)
└── pipeline/                       NEW - batch Feature Engineering Pipeline
    ├── base.py                     BaseFeatureModule, frame_to_feature_values()
    ├── validation.py               FeatureValidationIssue, FeaturePipelineValidator
    ├── price.py                    PriceFeatures            (full)
    ├── funding.py                  FundingFeatures          (full, serves standard + OI-weighted)
    ├── open_interest.py            OpenInterestFeatures     (full)
    ├── liquidation.py              LiquidationFeatures      (full)
    ├── long_short_ratio.py         LongShortRatioFeatures   (full, serves global + top-account + top-position)
    ├── premium_discount.py         PremiumDiscountFeatures  (framework only)
    ├── market_structure.py         MarketStructureFeatures  (framework only)
    ├── cvd.py                      CvdFeatures               (framework only)
    └── pipeline.py                 FeaturePipeline, FeaturePipelineResult

src/btengine/feature_store/
├── base.py                        (existing, modified) FeatureStore ABC — read() gained `version`
└── local_store.py                 (existing, modified) LocalFeatureStore — Parquet+DuckDB, versioned

tests/features/pipeline/            mirrors src/btengine/features/pipeline/, one file per module
tests/feature_store/test_local_store.py   (existing, extended with versioning tests)
```

Everything under `features/pipeline/` is new. Nothing in
`btengine.strategy`, `btengine.backtest`, or `btengine.data` was touched —
this layer only *reads* canonical records and *writes* `FeatureValue`s.

### Why a second `features/` subpackage instead of extending `FeatureAnalyzer`?

The pre-existing `FeatureAnalyzer` (in `features/base.py`) answers "what's
this feature's value **right now**" during a live backtest tick, given a
`HistoricalCandleSource` it can query for lookback. This task asks for the
opposite direction: given a **whole historical series**, produce the
**whole series of feature values** up front, for storage and reuse. Rather
than force one interface to do both jobs, `features/pipeline/` adds a
parallel, batch-oriented contract (`BaseFeatureModule.compute(symbol,
records) -> list[FeatureValue]`) that reuses the same `FeatureValue`
output type. Both can coexist: `FeatureAnalyzer` for live/tick-by-tick
use, the pipeline for bulk precomputation into the Feature Store.

## 2. The `FeatureValue` object

```python
@dataclass(frozen=True)
class FeatureValue:
    symbol: str
    feature_name: str      # namespaced "<module_name>.<column>", e.g. "price.atr_14"
    timestamp: datetime    # timezone-aware, UTC
    value: float
    version: str = "v1"    # which revision of the module's calculation produced this
```

This was the only change to an existing type in this task: an additive
`version` field (default `"v1"`, so every prior caller is unaffected),
needed because the task explicitly asked for Feature Store versioning.

Every module namespaces its output as `f"{module.module_name}.{column}"`
(e.g. `"funding_standard.funding_rate_sma_8"`,
`"long_short_ratio_top_account.long_short_ratio"`) so two modules can
never collide in the Feature Store, and one glance at a feature name says
which module and which CoinGlass data source produced it.

## 3. Feature modules

Every module is a stateless, pure class: `__init__` takes only rolling
window sizes (generic technical-analysis parameters, not strategy
thresholds) and, where one canonical schema type is shared by multiple
CoinGlass endpoints, a `source_label`. `compute(symbol, records)` takes a
chronological list of one canonical record type and returns a flat list
of `FeatureValue` — no I/O, no side effects, no knowledge of any other
module.

| Module | Input | Emits (namespaced under module name) |
|---|---|---|
| `PriceFeatures` (`price`) | `list[Candle]` | `return_pct`, `log_return`, `true_range`, `atr_{n}`, `sma_{n}`, `ema_{n}`, `volatility_{n}`, `high_low_range_pct` |
| `FundingFeatures` (`funding_{source_label}`) | `list[FundingRate]` | `funding_rate`, `funding_rate_change`, `funding_rate_sma_{n}`, `funding_rate_zscore_{n}` |
| `OpenInterestFeatures` (`open_interest`) | `list[OpenInterest]` | `open_interest`, `oi_change_pct`, `oi_sma_{n}`, `oi_roc_{n}`, `oi_zscore_{n}` |
| `LiquidationFeatures` (`liquidation`) | `list[Liquidation]` | `long_liquidation_usd`, `short_liquidation_usd`, `total_liquidation_usd`, `liquidation_imbalance`, and rolling sums of each over `n` bars |
| `LongShortRatioFeatures` (`long_short_ratio_{source_label}`) | `list[LongShortRatio]` | `long_account_ratio`, `short_account_ratio`, `long_short_ratio`, `long_short_ratio_change`, `long_short_ratio_sma_{n}`, `long_short_ratio_zscore_{n}` |
| `PremiumDiscountFeatures` (`premium_discount`) | — | `NotImplementedError` (needs paired spot price series) |
| `MarketStructureFeatures` (`market_structure`) | — | `NotImplementedError` (needs strategy-owner-supplied structure definition) |
| `CvdFeatures` (`cvd`) | — | `NotImplementedError` (needs taker buy/sell volume split not in the canonical schema) |

`FundingFeatures(source_label="standard")` and
`FundingFeatures(source_label="oi_weighted")` are the same class serving
CoinGlass's two funding-rate endpoints; likewise
`LongShortRatioFeatures(source_label="global"|"top_account"|"top_position")`
serves all three long/short ratio endpoints. This avoids three
near-identical classes for what is, structurally, the same computation
over the same schema.

### NaN/Inf handling

`frame_to_feature_values()` (in `pipeline/base.py`) is the one shared
helper every module funnels its computed `pandas.DataFrame` through. It
silently **omits** any cell that is `NaN`, `None`, or `inf` — e.g. before
a rolling window has enough history, or when a ratio is undefined
(`0/0`) — rather than emit a bad value. A feature simply doesn't exist yet
at that timestamp; it never exists *with* a wrong value.

## 4. Validation

`FeaturePipelineValidator` (in `pipeline/validation.py`) is a defensive
check on this layer's own output — input records are already validated by
the canonical schema before they arrive, so this checks what a
*computation* could get wrong:

- **NaN / infinite values** — should be unreachable given the filtering
  above, but checked in case a future module bypasses it.
- **Naive timestamps** — every `FeatureValue.timestamp` must be
  timezone-aware.
- **Duplicate records** — more than one value for the same `(symbol,
  feature_name, timestamp, version)`.
- **Non-monotonic series** — timestamps must be strictly increasing
  within each `(symbol, feature_name, version)` series (a windowing bug
  could otherwise silently reorder or repeat a timestamp).

`validate()` returns a list of `FeatureValidationIssue(severity,
feature_name, message)` — empty when everything is well-formed.

## 5. `FeaturePipeline` orchestrator

```python
pipeline = FeaturePipeline(
    modules=[PriceFeatures(), FundingFeatures(), OpenInterestFeatures(),
             LiquidationFeatures(), LongShortRatioFeatures()],
    feature_store=LocalFeatureStore(root),   # optional
)

result = pipeline.run(
    symbol="BTCUSDT",
    inputs={
        "price": candles,
        "funding_standard": funding_rates,
        "open_interest": open_interest_records,
        "liquidation": liquidations,
        "long_short_ratio_global": long_short_ratios,
    },
)
# result.features -> list[FeatureValue] (all modules combined)
# result.issues    -> list[FeatureValidationIssue]
# result.is_valid  -> False if any ERROR-severity issue was found
```

`inputs` maps each module's `module_name` to its input record series. A
module absent from `inputs` is skipped (so callers only need to supply
data for the modules they actually want run). If a `feature_store` was
configured and `persist=True` (the default), the combined feature list is
written to it after validation. The orchestrator has no branching logic
based on feature *values* — it only wires modules to inputs and fans out
results.

## 6. Feature Store: versioning

`LocalFeatureStore` (Parquet-per-`symbol`/`feature_name` file, queried via
DuckDB, unchanged in storage engine) now writes and reads a `version`
column:

- **Write**: dedupes on `(timestamp, version)` — two different versions
  of the same feature at the same timestamp **coexist**; rewriting the
  same `(timestamp, version)` overwrites just that row.
- **Read**: `store.read(..., version="v2")` filters to one version;
  omitting `version` returns every stored version.
- **Legacy files** written before this change (no `version` column) are
  transparently backfilled to `"v1"` on first write after this change.

This means a module's calculation can be revised (e.g. `PriceFeatures`
changes its ATR formula) by bumping the `version` passed into
`frame_to_feature_values(..., version="v2")` without silently overwriting
or mixing in the old values — old and new coexist under distinct
versions until a caller explicitly chooses one.

## 7. Integration with the Backtesting Engine

This layer produces the same `FeatureValue`/`FeatureStore` types the
Research Platform Architecture phase already wired into
`btengine.features.base.FeatureAnalyzer` and
`btengine.feature_store.base.FeatureStore`. Concretely:

- A historical run precomputes features once via `FeaturePipeline.run(...,
  feature_store=store)` for the full backtest date range.
- `BacktestEngine` (or a `FeatureAnalyzer` implementation) reads back
  exactly the slice it needs via `store.read(symbol=..., feature_name=...,
  start=..., end=...)` — no recomputation inside the simulation loop.
- Because the Feature Store's interface and on-disk format are
  provider-agnostic and strategy-agnostic, the same stored features are
  reusable, unmodified, by a future Demo Trading or Live Trading agent
  that only needs the *latest* value rather than a historical range.

No file in `btengine.backtest` or `btengine.strategy` was modified to
achieve this — integration is purely through the pre-existing
`FeatureValue`/`FeatureStore` contracts, which this task only extended
additively (the `version` field).

## 8. What this layer explicitly does not do

- No BUY/SELL signal generation.
- No scoring, weighting, or "is this a good setup" judgment.
- No GUI.
- No knowledge of any strategy rule, threshold, or spec
  (`btengine.strategy.*` is never imported here).

Waiting for approval before implementing Funding Rate strategy rules, per
the explicit instruction that closed this task.
