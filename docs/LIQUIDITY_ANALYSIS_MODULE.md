# Liquidity Analysis Module

Status: **Analysis only. No BUY/SELL signal, entry/exit logic, scoring,
or risk management has been implemented or assumed.** This module turns
liquidation history, positioning-ratio history, and read-only
open-interest/price context into one standardized `LiquidityAnalysis`
snapshot — descriptive statistics about liquidation volumes/imbalance,
positioning, crowdedness, participation, and liquidation-to-open-interest
pressure. It never judges whether current conditions are a good trade,
and it never decides to trade.

This module follows the same conventions as the previously completed
[Funding Rate](FUNDING_RATE_ANALYSIS_MODULE.md),
[Open Interest](OPEN_INTEREST_ANALYSIS_MODULE.md), and
[Premium & Discount](PREMIUM_DISCOUNT_ANALYSIS_MODULE.md) Analysis
Modules (decoupled input types, unset-by-default configuration
placeholders for genuinely proprietary choices, a `to_feature_map()`
bridge to the Strategy Framework). This document covers what's specific
to Liquidity — the largest of the four in scope, since it's the first to
combine multiple independent input sources and multiple exchanges in one
engine.

## 1. Folder structure

```
src/btengine/analysis/
└── liquidity/
    ├── __init__.py
    ├── config.py          LiquidityAnalysisConfig, AggregationMethod
    ├── models.py           LiquidationObservation, RatioObservation, OpenInterestObservation,
    │                        PriceObservation, LiquidityAnalysis
    ├── stats.py              compute_bias, aggregate_by_timestamp, zscore_of_latest,
    │                          half_split_delta, align_two_series — independently testable
    ├── validation.py           LiquidityValidationIssue, LiquidityDataValidator
    ├── integration.py           liquidation_observations_from_records(), ratio_observations_from_records(),
    │                            open_interest_observations_from_records(), price_observations_from_candles()
    ├── errors.py                 LiquidityAnalysisError
    └── engine.py                  LiquidityAnalysisEngine

tests/analysis/liquidity/   one test file per module above, 100% coverage
```

Nothing in `btengine.strategy`, `btengine.features`, `btengine.data`,
`btengine.backtest`, or any sibling `btengine.analysis.*` package was
modified.

## 2. Inputs

`LiquidityAnalysisEngine.analyze()` takes one required and five optional
keyword-only inputs, mirroring this task's INPUT section exactly:

| Parameter | Source | Required |
|---|---|---|
| `liquidations` | Liquidation History | **yes** |
| `global_ratio` | Global Long/Short Ratio | no |
| `top_trader_account_ratio` | Top Trader Account Ratio | no |
| `top_trader_position_ratio` | Top Trader Position Ratio | no |
| `open_interest` | Open Interest (read-only context) | no |
| `price` | Price History (read-only context) | no |

`global_ratio`, `top_trader_account_ratio`, and `top_trader_position_ratio`
all share the same `RatioObservation` type (the same canonical
`LongShortRatio` shape backs all three CoinGlass endpoints) — which
source a series represents is determined purely by which keyword
argument it's passed under. Omitting an optional input simply leaves its
dependent output fields `None` — see §5.

Every `*Observation` type carries its own `exchange` field (unlike the
single-exchange-per-call design of the Funding Rate/Open Interest/
Premium & Discount modules) since this module explicitly analyzes and
compares data across exchanges — see §3.

## 3. Multi-exchange support: selection, aggregation, and comparison

- **Exchange Selection** — `config.exchange_selection: tuple[str, ...] |
  None`. `None` (default) considers every exchange present in the given
  data; setting it restricts every computation (and the exchange
  comparison output) to just those exchanges.
- **Aggregation Method** — `config.aggregation_method: AggregationMethod`
  (`SUM` default, or `MEAN`). Whenever multiple exchanges report a
  reading at the same timestamp, this engine combines them with
  whichever method is configured, applied **uniformly** to every series
  it aggregates. `SUM` is the natural choice for volume-like metrics
  (liquidation USD — the market-wide total is the sum of every
  exchange's volume); `MEAN` is more natural for ratio-like metrics. The
  engine does not silently pick a different method per metric type
  (that would be an unstated assumption) — if you want `SUM` for
  liquidations and `MEAN` for ratios, run two `analyze()` calls with
  different configs and take the fields you need from each.
- **Exchange Comparison** — `LiquidityAnalysis.exchange_liquidation_totals:
  dict[str, float]` reports each exchange's total (long + short)
  liquidation volume within the analysis window, computed from the raw
  per-exchange records (before cross-exchange aggregation) so exchanges
  can be compared directly — purely descriptive, no judgment about which
  exchange's behavior is more "significant."

## 4. `LiquidityAnalysisConfig`

```python
@dataclass(frozen=True)
class LiquidityAnalysisConfig:
    analysis_window: int = 30
    spike_window: int = 30
    exchange_selection: tuple[str, ...] | None = None
    aggregation_method: AggregationMethod = AggregationMethod.SUM
    outlier_zscore_threshold: float | None = None    # TODO(owner): set to enable
    spike_zscore_threshold: float | None = None         # TODO(owner): set to enable
    expected_interval: timedelta | None = None             # TODO(owner): set to enable
```

`analysis_window` bounds every windowed computation (liquidation
volumes/bias, positioning, crowdedness baseline, participation, pressure,
shift, exchange comparison) uniformly — one generic lookback size, not a
per-responsibility parameter, to keep the configuration surface
manageable. `spike_window` is a separate, dedicated lookback specifically
for the liquidation-intensity/abnormal-spike baseline (mirroring the
Open Interest module's own distinct `spike_window`), since that baseline
may reasonably need to differ in size from the general analysis window.

## 5. Analysis responsibilities → output fields

Every named responsibility in this task maps onto one or more
`LiquidityAnalysis` fields. All cleaning (drop missing/invalid readings,
apply `exchange_selection`, dedupe by `(timestamp, exchange)` keeping the
last-given reading, sort chronologically) happens before any computation
below; a series with zero usable observations leaves its dependent
fields `None` (or, for `liquidations` specifically, raises
`LiquidityAnalysisError` — see §7).

| Responsibility | Field(s) | Definition |
|---|---|---|
| Liquidation Events | `liquidation_event_count`, `sample_size` | count of distinct (cross-exchange-aggregated) liquidation bars in the window |
| Long Liquidations | `long_liquidation_volume` | sum of aggregated long-liquidation USD over the window |
| Short Liquidations | `short_liquidation_volume` | sum of aggregated short-liquidation USD over the window |
| Liquidation Imbalance | `liquidation_bias` | `compute_bias(long_volume, short_volume)` — in `[-1, 1]`, `None` if both are zero |
| Liquidation Intensity | `liquidation_intensity` | `zscore_of_latest()` of the latest per-bar total liquidation vs. its own `spike_window` history |
| Abnormal Liquidation Events | `is_abnormal_liquidation` | `abs(liquidation_intensity) > spike_zscore_threshold`, or `None` if the threshold isn't configured or the intensity itself couldn't be computed |
| Long/Short Positioning | `long_short_ratio` | latest aggregated `global_ratio` reading's `long/short` (`None` if `short == 0`) |
| Long/Short Positioning (top trader) | `top_trader_account_bias`, `top_trader_position_bias`, `top_trader_bias` | bias of the latest aggregated reading from each source; `top_trader_bias` prefers `top_trader_position_ratio` over `top_trader_account_ratio` when both are given (position ratio is capital-weighted, the more direct measure of "top trader bias" — a data-source preference, not an invented trading rule), documented explicitly so nothing is hidden: both underlying figures remain available in their own fields |
| Crowded Market Conditions | `market_crowdedness` | `zscore_of_latest()` of the `global_ratio` bias series over the window — how statistically unusual current positioning skew is relative to its own recent history; a magnitude, never a directional trading call |
| Market Participation | `market_participation`, `current_open_interest` | `market_participation` = % change of aggregated Open Interest from the start to the end of the window (`None` with fewer than 2 readings or a zero starting value); `current_open_interest` is simply the latest aggregated reading |
| Liquidity Pressure | `liquidity_pressure` | total windowed liquidation volume ÷ average Open Interest over the same (liquidation, OI) joined window — "liquidations as a fraction of open interest," a standard descriptive derivatives-market concept |
| Liquidity Shift | `liquidity_shift` | `half_split_delta()` of the per-bar liquidation/OI ratio series — is that pressure trending up or down within the window |
| Exchange Comparison | `exchange_liquidation_totals` | see §3 |
| (read-only) Price History | `current_price` | latest aggregated `price` reading, `None` if omitted |
| — | `confidence_level` | `min(sample_size / max(analysis_window, spike_window, 1), 1.0)` — data sufficiency, not a trading-confidence score |

`liquidity_pressure`/`liquidity_shift` only consider bars where **both**
liquidation and Open Interest data exist at the same timestamp (an inner
join via `align_two_series`) — both are `None` if `open_interest` is
omitted or the two series never share a timestamp.

## 6. Validation

`LiquidityDataValidator.validate(...)` accepts the same six keyword
inputs as `analyze()` and checks, per source:

- **Missing liquidation data** / **missing ratio data** (per each of the
  three ratio sources) / missing Open Interest / missing price —
  `WARNING`.
- **Invalid timestamps** (naive/non-timezone-aware) — `ERROR`.
- **Duplicate records** — keyed by `(timestamp, exchange)`, so the same
  timestamp from two different exchanges is expected, not a duplicate —
  `ERROR`.
- **Exchange inconsistencies** — if `exchange_selection` is configured,
  any selected exchange absent from *every* provided source is flagged —
  `WARNING`.
- **Outlier values** — opt-in via `outlier_zscore_threshold`, applied to
  total liquidation volume, `long_account_ratio`, Open Interest, and
  price independently — `WARNING`.
- **Timestamp gaps** — opt-in via `expected_interval`, checked
  per-exchange (a gap only makes sense within one exchange's own
  chronological series) — `WARNING`.

## 7. Errors

`analyze()` raises `LiquidityAnalysisError` only when `liquidations`
has no usable reading after cleaning — liquidation data is this
module's one required input, so nothing meaningful can be produced
without it. Every other source is optional; omitting it (or it being
entirely missing/invalid) simply leaves its dependent fields `None`
rather than raising.

## 8. Integration with the Feature Layer

```python
from btengine.analysis.liquidity.integration import (
    liquidation_observations_from_records, ratio_observations_from_records,
    open_interest_observations_from_records, price_observations_from_candles,
)
from btengine.analysis.liquidity.engine import LiquidityAnalysisEngine

analysis = LiquidityAnalysisEngine().analyze(
    "BTCUSDT",
    liquidations=liquidation_observations_from_records(liquidation_records),
    global_ratio=ratio_observations_from_records(global_ratio_records),
    top_trader_account_ratio=ratio_observations_from_records(top_account_records),
    top_trader_position_ratio=ratio_observations_from_records(top_position_records),
    open_interest=open_interest_observations_from_records(oi_records),
    price=price_observations_from_candles(candle_records),
)
```

Each adapter accepts exactly the canonical record type that flows into
the corresponding Feature Engineering Layer module —
`liquidation_observations_from_records` takes the same
`Sequence[Liquidation]` `LiquidationFeatures` consumes,
`ratio_observations_from_records` the same `Sequence[LongShortRatio]`
`LongShortRatioFeatures` consumes (reused for all three ratio sources),
`open_interest_observations_from_records` the same `Sequence[OpenInterest]`
`OpenInterestFeatures` consumes, and `price_observations_from_candles`
the same `Sequence[Candle]` `PriceFeatures` consumes. None of them filter
by exchange or symbol — pass only the records for the symbol you're
analyzing; `exchange_selection` then narrows which exchanges are
considered.

## 9. Integration with the Strategy Framework

No dedicated `RuleSet` exists yet for Liquidity in `btengine.strategy.rules`
(the closest existing category, `liquidity.py`, is the same
no-condition-content-yet `RuleSet` pattern as every other rule category
built in the Strategy Specification Framework phase). As with every
prior analysis module, no condition evaluator exists in this codebase
yet; `RuleCondition.feature` is a named lookup key for one to resolve
later.

`LiquidityAnalysis.to_feature_map()` bridges the two: every numeric field
is flattened into a `"liquidity_analysis.<field>"` key,
`is_abnormal_liquidation` is represented as `1.0`/`0.0` when known, and
`exchange_liquidation_totals` is flattened into one
`"liquidity_analysis.exchange_liquidation_total.<exchange>"` key per
exchange, e.g.:

```python
{
    "liquidity_analysis.long_liquidation_volume": 4_200_000.0,
    "liquidity_analysis.liquidation_bias": 0.18,
    "liquidity_analysis.liquidation_intensity": 2.4,
    "liquidity_analysis.market_crowdedness": 1.1,
    "liquidity_analysis.liquidity_pressure": 0.014,
    "liquidity_analysis.exchange_liquidation_total.BINANCE": 2_600_000.0,
    "liquidity_analysis.exchange_liquidation_total.OKX": 1_600_000.0,
    "liquidity_analysis.confidence_level": 1.0,
    ...
}
```

No rule content or threshold was added to `LiquidityRules` — only this
bridging convention is documented.

## 10. Future extension points

This task explicitly asks the module to "support future extensions for"
four capabilities. None of the four have a canonical schema in
`btengine.data.schema` yet (no order book, taker buy/sell split, or
position-flow record types exist), so no stub classes or half-built
interfaces were added for them — that would be hollow scaffolding for
data this codebase can't yet represent. Instead, the architecture already
accommodates each one without a breaking change, by design:

- **Liquidation Heatmaps** — a heatmap is a 2D view (price level ×
  time) of liquidation density; once a canonical schema for
  price-bucketed liquidation data exists, it's a new `*Observation` type
  and a new keyword-only `analyze()` parameter (e.g.
  `liquidation_heatmap: Sequence[LiquidationHeatmapObservation] = ()`),
  following exactly the pattern the six existing inputs already use.
- **Order Book Liquidity** — same shape: a new `OrderBookObservation`
  type (bid/ask depth at a timestamp) and a new optional `analyze()`
  parameter; `stats.py`'s generic helpers (`aggregate_by_timestamp`,
  `zscore_of_latest`) already work on any `(timestamp, float)` series, so
  depth-based statistics would reuse them directly.
- **Taker Buy/Sell Volume** — a new `TakerVolumeObservation` type; the
  existing `compute_bias()` helper directly computes a buy/sell
  imbalance from it with no new formula needed (this is exactly the same
  shape as `liquidation_bias`).
- **Net Position Flow** — derived from Open Interest change combined
  with price direction; `market_participation`'s OI-change computation
  is the starting primitive this would extend.

Adding any of these is additive (a new optional keyword parameter, a new
`*Observation` type, new output fields defaulting existing callers to
unaffected) rather than a breaking change to `analyze()`'s existing
signature, since every current input is already optional except
`liquidations`.

## 11. What this module explicitly does not do

- No BUY/SELL signal generation.
- No composite scoring (`confidence_level` is about data sufficiency,
  not a trade-confidence score; `liquidation_intensity`/
  `market_crowdedness` are magnitude statistics, not scores).
- No entry or exit logic.
- No risk management (position sizing, stop placement, etc.).
- No invented thresholds — `outlier_zscore_threshold`,
  `spike_zscore_threshold`, and `expected_interval` are unset
  placeholders; supply your own rule to enable that behavior.
- No GUI.

Waiting for approval before implementing the Scoring Engine.
