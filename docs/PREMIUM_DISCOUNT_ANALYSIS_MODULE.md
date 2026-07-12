# Premium & Discount Analysis Module

Status: **Range classification only. No BUY/SELL signal, score, entry,
exit, or proprietary rule has been implemented or assumed.** This module
identifies an active trading range from swing highs/lows and classifies
where the current price sits within it (Discount / Equilibrium /
Premium / above / below the range). It never judges whether that
position is a good trade, and it never decides to trade.

This module follows the same conventions as the previously completed
[Funding Rate](FUNDING_RATE_ANALYSIS_MODULE.md) and
[Open Interest](OPEN_INTEREST_ANALYSIS_MODULE.md) Analysis Modules (a
decoupled input type, unset-by-default configuration placeholders for
genuinely proprietary choices, a `to_feature_map()` bridge to the
Strategy Framework). This document covers what's specific to Premium &
Discount.

## 1. Folder structure

```
src/btengine/analysis/
└── premium_discount/
    ├── __init__.py
    ├── config.py          PremiumDiscountAnalysisConfig, SwingDetectionMethod
    ├── models.py           CandleObservation, SwingKind, SwingPoint, PremiumDiscountZone, PremiumDiscountAnalysis
    ├── swings.py             detect_swings() — independently testable swing detection
    ├── validation.py           PremiumDiscountValidationIssue, PremiumDiscountValidator
    ├── integration.py           observations_from_candles()
    ├── errors.py                 PremiumDiscountAnalysisError
    └── engine.py                  PremiumDiscountAnalysisEngine

tests/analysis/premium_discount/   one test file per module above, 100% coverage
```

Nothing in `btengine.strategy`, `btengine.features`, `btengine.data`,
`btengine.backtest`, or either sibling `btengine.analysis.funding_rate`/
`btengine.analysis.open_interest` package was modified. The Feature
Layer's own framework-only `btengine.features.pipeline.premium_discount.PremiumDiscountFeatures`
stub (built earlier, still `NotImplementedError` — it needs a paired
spot price series this module doesn't require) is untouched and
unrelated to this module.

## 2. Core analysis: swing points → active range → zones

1. **Swing High / Swing Low** — `swings.py` scans the last
   `swing_lookback` candles and returns confirmed `SwingPoint`s (see §3).
2. **Active Trading Range** — `active_high` = the highest confirmed
   swing-high price in that window; `active_low` = the lowest confirmed
   swing-low price. This is a deliberately simple, symmetric definition
   ("the range spans the most extreme confirmed points in the lookback")
   — not a market-structure rule about which swing should "count" as
   structurally significant (that judgment is explicitly out of scope;
   see `btengine.features.pipeline.market_structure.MarketStructureFeatures`,
   still a framework-only stub for exactly this reason).
3. **Midpoint (50%)** — `midpoint = active_low + (active_high - active_low) * midpoint_ratio`,
   defaulting to the conventional 50% but fully configurable.
4. **Discount / Equilibrium / Premium Zone** and **Current Price
   Position** — see §5.

## 3. Swing detection methods

`SwingDetectionMethod` currently implements two standard techniques
(configurable via `swing_detection_method`); a value outside these two
raises `NotImplementedError` rather than silently falling back to a
guess, so a future method must be deliberately implemented, never
assumed:

- **`FRACTAL`** (default) — an n-bar local extremum. A candle at index
  `i` confirms as a swing high if its `high` is strictly greater than
  every candle within `swing_strength` bars on *both* sides (swing low:
  symmetric, using `low` and `<`). This is a **no-repaint** definition:
  once a candle has `swing_strength` bars of future context available,
  whether it's confirmed never changes as more data arrives later — see
  §7, "historical replay consistency."
- **`EXTREMUM`** — simply the single highest `high` and single lowest
  `low` candle in the window. No confirmation delay; always available
  given at least one candle. Useful when you want the range to react
  immediately to a new extreme rather than wait for fractal confirmation.

Both are independently unit-tested in `tests/analysis/premium_discount/test_swings.py`
against `detect_swings()` directly (per this task's "unit tests for:
Swing detection" requirement), separate from the engine's own tests.

## 4. `PremiumDiscountAnalysisConfig`

```python
@dataclass(frozen=True)
class PremiumDiscountAnalysisConfig:
    swing_detection_method: SwingDetectionMethod = SwingDetectionMethod.FRACTAL
    swing_lookback: int = 50
    swing_strength: int = 2
    midpoint_ratio: float = 0.5
    equilibrium_band_pct: float | None = None        # TODO(owner): set to enable a real EQUILIBRIUM zone
    outlier_zscore_threshold: float | None = None      # TODO(owner): set to enable
    expected_interval: timedelta | None = None            # TODO(owner): set to enable
```

`swing_lookback` / `swing_strength` are generic lookback sizes, not
trading rules. `midpoint_ratio` is a structural parameter (0 = at
`active_low`, 1 = at `active_high`) rather than a business threshold —
50% is the universal convention, but it's adjustable.

`equilibrium_band_pct` is the one genuinely proprietary choice in this
module: how wide (as a fraction of the range) the "equilibrium" zone
around the midpoint should be has no universal answer — different
traders use different widths, and some use none at all. It defaults to
`None`: with no band configured, only a price exactly at the midpoint
classifies as `EQUILIBRIUM` (a boundary case); everything else is
`DISCOUNT` or `PREMIUM`. Once you supply a width (e.g. `0.05` for a band
spanning 47.5%–52.5% of the range), `EQUILIBRIUM` becomes a real,
reachable zone.

`FRACTAL` additionally requires `swing_lookback >= 2 * swing_strength +
1` (validated at construction) — a candidate index needs that many bars
in the window to have `swing_strength` bars on both sides; `EXTREMUM`
has no such constraint.

## 5. Analysis — `PremiumDiscountAnalysisEngine.analyze(symbol, candles)`

Cleans the input first (drops candles with a missing `high`/`low`/`close`
or an internally invalid one where `high < low`; sorts chronologically;
keeps the last-given candle for a duplicate timestamp), then:

1. Runs `detect_swings()` over the cleaned series.
2. Computes `active_high` / `active_low` / `range_size` / `midpoint`.
3. `current_price` = the most recent candle's `close`.
4. `current_price_position_pct = (current_price - active_low) / range_size * 100`
   — 0% at `active_low`, 100% at `active_high`; can go outside `[0, 100]`
   if price has moved beyond the identified range (not clamped, so no
   information is hidden).
5. **Zone** (`PremiumDiscountZone`): `ABOVE_RANGE` if `current_price >
   active_high`; `BELOW_RANGE` if `current_price < active_low`;
   otherwise `EQUILIBRIUM` if within the configured band (or exactly at
   the midpoint when no band is configured); otherwise `PREMIUM` (above
   midpoint) or `DISCOUNT` (below).
6. **`premium_percentage`** / **`discount_percentage`** — how deep into
   its own half of the range the price sits, as a percentage of that
   half's span (`0%` at the midpoint, `100%` at the corresponding
   extreme, and *not* capped at 100% if price is outside the range). The
   side that doesn't apply is `0.0`; a field is only `None` when its
   span is mathematically zero (e.g. `midpoint_ratio=1.0` makes the
   "premium span" `active_high - midpoint == 0`).
7. **`confidence_level`** — `min(sample_size / max(swing_lookback, 2 *
   swing_strength + 1, 1), 1.0)`, a data-sufficiency measure, not a
   trading-confidence score.

`analyze()` raises `PremiumDiscountAnalysisError` in three cases: no
usable candle after cleaning; no confirmed swing high *and* swing low
within the lookback (nothing to build a range from); or a computed
`active_high <= active_low` (a degenerate, zero-or-negative-width range
— nothing meaningful can be classified against it).

## 6. Multi-timeframe support

`PremiumDiscountAnalysisEngine` takes a `timeframe_label` constructor
parameter (default `"unspecified"`) — the same `source_label` pattern
used by the Funding Rate and Open Interest engines. The computation
itself has no concept of timeframe; a caller runs one engine instance
per timeframe (e.g. one for `"1h"` candles, one for `"4h"`) and gets back
independently labeled `PremiumDiscountAnalysis` results. This module
takes no position on how multiple timeframes' results should be
combined or reconciled — that would be a strategy decision, out of
scope here.

## 7. Historical replay consistency (no repaint)

Because `FRACTAL` confirmation only ever looks backward plus a **fixed**
number of forward bars, a swing point's confirmation status and value
never change once confirmed — replaying the same candle series
incrementally (as a backtest would) never retroactively rewrites an
already-reported `active_high`/`active_low` for a point that has already
gathered enough future context. `tests/analysis/premium_discount/test_engine.py::test_historical_replay_never_repaints_a_confirmed_swing`
verifies this directly: it analyzes growing prefixes of the same series
and asserts a swing confirmed early stays identical at every later,
longer prefix.

## 8. Integration with the Feature Layer

```python
from btengine.analysis.premium_discount.integration import observations_from_candles
from btengine.analysis.premium_discount.engine import PremiumDiscountAnalysisEngine

candles = candle_feed.get_candles(symbol="BTCUSDT", timeframe=Timeframe.HOUR_1, ...)
observations = observations_from_candles(candles)
analysis = PremiumDiscountAnalysisEngine(timeframe_label="1h").analyze("BTCUSDT", observations)
```

`observations_from_candles` accepts the same `Sequence[Candle]` type
that `btengine.features.pipeline.price.PriceFeatures` (the Feature
Engineering Layer's price module) consumes — the normalized, canonical
OHLC series flowing through that layer. A full OHLC bar isn't a single
named `FeatureValue`, so unlike the Funding Rate/Open Interest modules
this integration point adapts directly from `Candle`, not from a
computed feature series.

## 9. Integration with the Strategy Framework

No `RuleSet` currently exists for Premium/Discount rules in
`btengine.strategy.rules` (the 16 rule categories built in the Strategy
Specification Framework phase cover Premium/Discount via
`btengine/strategy/rules/premium_discount.py`, a `RuleSet` with no
condition content defined yet — pure structure, same as every other rule
category). As with the Funding Rate and Open Interest modules, no
condition evaluator exists in this codebase yet; `RuleCondition.feature`
is a named lookup key for one to resolve later.

`PremiumDiscountAnalysis.to_feature_map()` bridges the two. Numeric
fields are flattened into `"premium_discount_analysis_<timeframe>.<field>"`
keys; the categorical `zone` is one-hot encoded into
`zone_is_discount` / `zone_is_equilibrium` / `zone_is_premium` /
`zone_is_above_range` / `zone_is_below_range` flags (`1.0`/`0.0`) so a
future numeric `RuleCondition` (`GT`/`LT`/`EQ`/...) can reference any of
them, e.g.:

```python
{
    "premium_discount_analysis_1h.active_high": 71250.0,
    "premium_discount_analysis_1h.midpoint": 69500.0,
    "premium_discount_analysis_1h.current_price_position_pct": 62.3,
    "premium_discount_analysis_1h.zone_is_premium": 1.0,
    "premium_discount_analysis_1h.zone_is_discount": 0.0,
    "premium_discount_analysis_1h.confidence_level": 1.0,
    ...
}
```

The `timeframe` segment keeps results from different timeframes (per
§6) from colliding when several are computed for the same symbol. No
rule content or threshold was added to `PremiumDiscountRules` — only
this bridging convention is documented.

## 10. What this module explicitly does not do

- No BUY/SELL signal generation.
- No scoring (`confidence_level` is about data sufficiency, not a
  trade-confidence score).
- No entry or exit logic.
- No invented thresholds — `equilibrium_band_pct`,
  `outlier_zscore_threshold`, and `expected_interval` are unset
  placeholders; supply your own rule to enable that behavior.
- No market-structure judgment about which swings are "significant"
  beyond the simple extremum-of-confirmed-swings rule in §2 (that
  remains `btengine.features.pipeline.market_structure.MarketStructureFeatures`'s
  job, still a framework-only stub).
- No GUI.

Waiting for approval before implementing the Liquidity Analysis Module.
