# Funding Rate Analysis Module

Status: **Analysis only. No BUY/SELL signal, threshold, or score has been
implemented or assumed.** This module turns a funding rate history into a
standardized `FundingAnalysis` snapshot — a set of descriptive statistics
about the series (direction, dispersion, historical range, and how much
data backed the result). It never judges whether a value is bullish or
bearish, and it never decides to trade.

## 1. Folder structure

```
src/btengine/analysis/
├── __init__.py
└── funding_rate/
    ├── __init__.py
    ├── config.py          FundingRateAnalysisConfig
    ├── models.py           FundingRateObservation, FundingDirection, FundingAnalysis
    ├── validation.py        FundingDataValidationIssue, FundingDataValidator
    ├── integration.py       observations_from_feature_values(), observations_from_funding_rates()
    ├── errors.py             FundingRateAnalysisError
    └── engine.py              FundingRateAnalysisEngine

tests/analysis/funding_rate/   one test file per module above, 100% coverage
```

`src/btengine/analysis/` is a new top-level package for standardized,
strategy-agnostic analysis engines — this is the first of several
(Open Interest, etc. to follow once approved). Nothing in
`btengine.strategy`, `btengine.backtest`, `btengine.features`, or
`btengine.data` was modified to build this.

## 2. Why a new input type instead of reusing `FeatureValue`?

The engine's own input type, `FundingRateObservation` (`timestamp`,
`funding_rate: float | None`), is deliberately smaller than both
`btengine.features.base.FeatureValue` (which carries `symbol`,
`feature_name`, and `version` — irrelevant to a pure funding-rate
computation) and the canonical `btengine.data.schema.FundingRate`
(which carries `exchange` — provider-specific). Decoupling from both
keeps `FundingRateAnalysisEngine` genuinely reusable — the task's
explicit objective — rather than binding the "reusable engine" to one
upstream shape.

`funding_rate: float | None` (rather than omitting missing readings from
the sequence) lets the engine's validator explicitly detect and report a
*known* missing value, distinct from a timestamp that was never expected
to exist.

## 3. `FundingRateAnalysisConfig`

```python
@dataclass(frozen=True)
class FundingRateAnalysisConfig:
    trend_window: int = 8
    momentum_window: int = 8
    volatility_window: int = 30
    historical_window: int | None = None       # None -> use all given history
    outlier_zscore_threshold: float | None = None   # TODO(owner): set to enable
    expected_interval: timedelta | None = None       # TODO(owner): set to enable
```

`trend_window` / `momentum_window` / `volatility_window` are generic
statistical lookback sizes — the same kind of parameter as an SMA/ATR
period elsewhere in this codebase — not a trading rule. `historical_window`,
`outlier_zscore_threshold`, and `expected_interval` are **explicit
placeholders**: they default to `None`, and the corresponding behavior
(bounding the historical stats window, outlier detection, gap detection)
is simply skipped until you supply a value. Nothing is assumed on your
behalf.

## 4. Validation — `FundingDataValidator`

`FundingDataValidator.validate(observations)` returns a list of
`FundingDataValidationIssue(severity, message, timestamp)` and checks:

| Check | Severity | Notes |
|---|---|---|
| Missing value (`funding_rate is None`) | `WARNING` | |
| Naive (non-timezone-aware) timestamp | `ERROR` | |
| Duplicate timestamp | `ERROR` | |
| Outlier (`|z-score| > outlier_zscore_threshold`) | `WARNING` | Skipped entirely unless `outlier_zscore_threshold` is configured |
| Gap (`interval > expected_interval`) | `WARNING` | Skipped entirely unless `expected_interval` is configured |

`FundingRateAnalysisEngine.validate(...)` exposes this directly; call it
before (or instead of) `analyze(...)` when you want to surface data
quality problems rather than silently work around them.

## 5. Analysis — `FundingRateAnalysisEngine.analyze(symbol, observations)`

`analyze()` first cleans the input (drops `None` readings, sorts
chronologically, and — for a duplicate timestamp — keeps whichever
reading was *last given* in the input sequence), then computes:

| Field | Definition |
|---|---|
| `current_funding` | Most recent reading |
| `previous_funding` | Second-most-recent reading (`None` if only one) |
| `funding_change` | `current - previous` |
| `funding_change_pct` | `funding_change / previous` (`None` if `previous == 0`) |
| `funding_trend` / `funding_trend_value` | Direction / value of a linear-regression slope over the last `trend_window` readings |
| `funding_momentum` / `funding_momentum_value` | Direction / value of `mean(second half) - mean(first half)` of the last `momentum_window` readings (whether the level is accelerating or decelerating) |
| `funding_volatility` | Sample standard deviation of the last `volatility_window` readings |
| `historical_average` / `historical_maximum` / `historical_minimum` | Over `historical_window` readings, or the entire given history if unset |
| `sample_size` | Count of usable (non-missing) readings used |
| `confidence_level` | `min(sample_size / max(configured windows), 1.0)` — a **data-sufficiency** measure, not a trading-confidence score |

`funding_trend` / `funding_momentum` are one of `RISING` / `FALLING` /
`FLAT` / `UNKNOWN` (`UNKNOWN` when fewer than 2 readings are available in
the relevant window) — a mathematical description of the computed
value's sign, not a bullish/bearish interpretation. Any window with fewer
than 2 usable readings yields `UNKNOWN`/`None` rather than a value
computed from insufficient data.

`analyze()` raises `FundingRateAnalysisError` if no usable reading
remains after cleaning — there is no meaningful `FundingAnalysis` to
return for an empty series.

## 6. Integration with the Feature Layer

```python
from btengine.analysis.funding_rate.integration import observations_from_feature_values
from btengine.analysis.funding_rate.engine import FundingRateAnalysisEngine

funding_features = [v for v in feature_store.read(
    symbol="BTCUSDT", feature_name="funding_standard.funding_rate", start=..., end=...,
)]
observations = observations_from_feature_values(funding_features)
analysis = FundingRateAnalysisEngine().analyze("BTCUSDT", observations)
```

`observations_from_feature_values` consumes exactly the `funding_rate`
series produced by `btengine.features.pipeline.funding.FundingFeatures`
(the Feature Engineering Layer built previously) — the caller filters to
one `feature_name` (e.g. `"funding_standard.funding_rate"` or
`"funding_oi_weighted.funding_rate"`) and this module does the rest.

`observations_from_funding_rates` is a second, direct path from the
canonical `btengine.data.schema.FundingRate` records, for callers with no
Feature Layer stage in between.

## 7. Integration with the Strategy Framework

`btengine.strategy.rules.funding_rate.FundingRateRules` is a `RuleSet` of
`RuleCondition(feature: str, operator, value)` entries — pure structure,
with no condition content defined yet (the strategy owner supplies rules
into `config/strategy/rules/funding_rate.yaml` later). No condition
evaluator exists yet in this codebase; `RuleCondition.feature` is just a
named lookup key it will resolve once one is built.

`FundingAnalysis.to_feature_map()` bridges the two: it flattens every
numeric field into a `"funding_rate_analysis.<field>" -> value` dict
(omitting fields that are `None`), e.g.:

```python
{
    "funding_rate_analysis.current_funding": 0.00012,
    "funding_rate_analysis.funding_trend_value": 0.00003,
    "funding_rate_analysis.funding_volatility": 0.00004,
    "funding_rate_analysis.confidence_level": 1.0,
    ...
}
```

Once a `RuleCondition` evaluator exists, a condition can reference any of
these names (e.g. `feature="funding_rate_analysis.funding_trend_value"`)
without this module needing to change. This module never writes to
`btengine.strategy`, and no rule content or threshold was added to
`FundingRateRules` — only this bridging convention is documented.

## 8. What this module explicitly does not do

- No BUY/SELL signal generation.
- No scoring or weighting (`confidence_level` is about data sufficiency,
  not a trade-confidence score).
- No bullish/bearish interpretation of any computed value.
- No invented thresholds — `outlier_zscore_threshold` and
  `expected_interval` are unset placeholders; supply your own rule to
  enable that behavior.
- No GUI.

Waiting for approval before implementing the Open Interest module.
