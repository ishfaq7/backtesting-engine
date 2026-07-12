# Open Interest Analysis Module

Status: **Analysis only. No BUY/SELL signal, threshold, or score has been
implemented or assumed.** This module turns an Open Interest history into
a standardized `OpenInterestAnalysis` snapshot — descriptive statistics
about the series (direction, dispersion, historical range, how unusual
the latest change was, and how much data backed the result). It never
judges whether a value is bullish or bearish, and it never decides to
trade.

This module mirrors the structure and conventions of the previously
completed [Funding Rate Analysis Module](FUNDING_RATE_ANALYSIS_MODULE.md)
— see that document for the general design rationale (a decoupled input
type, unset-by-default configuration placeholders, "raw value + optional
classification" pattern). This document covers what's specific to Open
Interest.

## 1. Folder structure

```
src/btengine/analysis/
└── open_interest/
    ├── __init__.py
    ├── config.py          OpenInterestAnalysisConfig
    ├── models.py           OpenInterestObservation, OiDirection, OpenInterestAnalysis
    ├── validation.py        OpenInterestDataValidationIssue, OpenInterestDataValidator
    ├── integration.py        observations_from_feature_values(), observations_from_open_interest_records()
    ├── errors.py              OpenInterestAnalysisError
    └── engine.py               OpenInterestAnalysisEngine

tests/analysis/open_interest/   one test file per module above, 100% coverage
```

Nothing in `btengine.strategy`, `btengine.features`, `btengine.data`, or
`btengine.backtest` — nor the sibling `btengine.analysis.funding_rate`
package — was modified to build this.

## 2. Supporting exchange-specific and aggregated Open Interest

`OpenInterestAnalysisEngine` takes a `source_label` constructor
parameter (default `"aggregated"`) — the same pattern the Feature
Engineering Layer's `FundingFeatures`/`LongShortRatioFeatures` use to
serve multiple CoinGlass sources from one class:

```python
aggregated_engine = OpenInterestAnalysisEngine()                       # source_label="aggregated"
binance_engine = OpenInterestAnalysisEngine(source_label="binance")     # exchange-specific
```

The computation is identical either way — only the `source` field on the
output `OpenInterestAnalysis` (and the namespace used by
`to_feature_map()`) differs. Callers construct one engine per Open
Interest series they want analyzed (one for the aggregated total, one
per exchange, as needed) and feed each its own observation history.

## 3. `OpenInterestObservation` and `OiDirection`

Same rationale as the Funding Rate module's `FundingRateObservation`:
`OpenInterestObservation(timestamp, open_interest: float | None)` is a
minimal type decoupled from both `btengine.data.schema.OpenInterest`
(exchange-specific) and `btengine.features.base.FeatureValue`
(symbol/feature-name/version namespaced), so the engine works for either
input shape and either OI source. `OiDirection` (`RISING` / `FALLING` /
`FLAT` / `UNKNOWN`) is a fresh, module-local enum — describing the sign
of a computed number, never a trading interpretation of it.

## 4. `OpenInterestAnalysisConfig`

```python
@dataclass(frozen=True)
class OpenInterestAnalysisConfig:
    trend_window: int = 8
    momentum_window: int = 8
    volatility_window: int = 30
    spike_window: int = 30
    historical_window: int | None = None            # None -> use all given history
    outlier_zscore_threshold: float | None = None    # TODO(owner): set to enable
    spike_zscore_threshold: float | None = None       # TODO(owner): set to enable
    expected_interval: timedelta | None = None          # TODO(owner): set to enable
```

`trend_window` / `momentum_window` / `volatility_window` / `spike_window`
are generic statistical lookback sizes, not trading rules. The three
`None`-by-default fields are explicit placeholders exactly like the
Funding Rate module's: the corresponding behavior is skipped (or the
corresponding output field stays unset) until you supply a value.

## 5. Validation — `OpenInterestDataValidator`

Identical check set to the Funding Rate module, applied to Open
Interest readings: missing values (`WARNING`), naive timestamps
(`ERROR`), duplicate timestamps (`ERROR`), outliers
(`WARNING`, opt-in via `outlier_zscore_threshold`), and gaps
(`WARNING`, opt-in via `expected_interval`).

This validator flags an Open Interest **level** that looks like bad
data. It is distinct from the engine's `is_abnormal_spike` analysis
output below, which measures how unusual the latest **change** was —
a descriptive statistic about real data, not a data-quality judgment.

## 6. Analysis — `OpenInterestAnalysisEngine.analyze(symbol, observations)`

Cleans the input the same way the Funding Rate engine does (drops
`None` readings, sorts chronologically, keeps the last-given reading for
a duplicate timestamp), then computes:

| Field | Definition |
|---|---|
| `current_oi` | Most recent reading |
| `previous_oi` | Second-most-recent reading (`None` if only one) |
| `oi_change` | `current - previous` |
| `oi_change_pct` | `oi_change / previous` (`None` if `previous == 0`) |
| `oi_trend` / `oi_trend_value` | Direction / value of a linear-regression slope over the last `trend_window` readings |
| `oi_momentum` / `oi_momentum_value` | Direction / value of `mean(second half) - mean(first half)` of the last `momentum_window` readings |
| `oi_volatility` | Sample standard deviation of the last `volatility_window` readings |
| `is_abnormal_spike` / `spike_magnitude` | See §7 below |
| `historical_average` / `historical_maximum` / `historical_minimum` | Over `historical_window` readings, or the entire given history if unset |
| `sample_size` | Count of usable (non-missing) readings used |
| `confidence_level` | `min(sample_size / max(configured windows), 1.0)` — a data-sufficiency measure, not a trading-confidence score |

Any window with fewer than 2 usable readings yields `UNKNOWN`/`None`
rather than a value computed from insufficient data. `analyze()` raises
`OpenInterestAnalysisError` if no usable reading remains after cleaning.

Open Interest values can range from single-digit contract counts to
billions of dollars of notional, so the `RISING`/`FALLING`/`FLAT`
classification uses a floating-point noise tolerance that scales with
the magnitude of the data being compared (rather than one fixed
constant) — this is numerical hygiene, not a trading threshold: it only
absorbs linear-algebra rounding noise on an exactly-flat series, never
influences a genuinely nonzero result.

## 7. Abnormal spike detection

`spike_magnitude` measures how many standard deviations the **latest
change** in Open Interest sits from the mean of the changes immediately
preceding it (both drawn from the last `spike_window` readings):

1. Take the last `spike_window` Open Interest levels and compute their
   consecutive differences (`changes`).
2. Split into `baseline` (every change except the most recent) and
   `latest_change` (the most recent one).
3. `spike_magnitude = (latest_change - mean(baseline)) / stdev(baseline)`.

`spike_magnitude` is computed whenever there's enough history (at least
2 baseline changes with nonzero spread) — **independent of
configuration**, since it's just a statistic. `is_abnormal_spike` is a
boolean classification of that statistic and only becomes `True`/`False`
once `spike_zscore_threshold` is configured; until then it stays `None`
rather than being classified against an invented cutoff, per this task's
"expose a configurable placeholder" instruction.

## 8. Integration with the Feature Layer

```python
from btengine.analysis.open_interest.integration import observations_from_feature_values
from btengine.analysis.open_interest.engine import OpenInterestAnalysisEngine

oi_features = feature_store.read(
    symbol="BTCUSDT", feature_name="open_interest.open_interest", start=..., end=...,
)
observations = observations_from_feature_values(oi_features)
analysis = OpenInterestAnalysisEngine().analyze("BTCUSDT", observations)
```

`observations_from_feature_values` consumes the `open_interest` series
produced by `btengine.features.pipeline.open_interest.OpenInterestFeatures`
(the Feature Engineering Layer). `observations_from_open_interest_records`
is a second, direct path from canonical `btengine.data.schema.OpenInterest`
records for callers with no Feature Layer stage in between. Neither
function filters by source — that's the caller's responsibility (e.g.
select the feature series or provider records for one specific exchange,
or for the aggregated endpoint) before construction; the engine's
`source_label` is then just the label attached to the result.

## 9. Integration with the Strategy Framework

`btengine.strategy.rules.open_interest.OpenInterestRules` is a `RuleSet`
of `RuleCondition(feature: str, operator, value)` entries — pure
structure, no condition content defined yet. As with the Funding Rate
module, no condition evaluator exists in this codebase yet;
`RuleCondition.feature` is just a named lookup key for one to resolve
later.

`OpenInterestAnalysis.to_feature_map()` bridges the two, flattening every
numeric field (and `is_abnormal_spike` as `1.0`/`0.0` when known) into a
`"open_interest_analysis_<source>.<field>" -> value` dict, e.g.:

```python
{
    "open_interest_analysis_aggregated.current_oi": 1_250_000_000.0,
    "open_interest_analysis_aggregated.oi_trend_value": 4_200_000.0,
    "open_interest_analysis_aggregated.spike_magnitude": 0.8,
    "open_interest_analysis_aggregated.confidence_level": 1.0,
    ...
}
```

The `source` segment (`aggregated`, `binance`, ...) keeps
exchange-specific and aggregated results from colliding when both are
computed for the same symbol. Once a `RuleCondition` evaluator exists, a
condition can reference any of these names without this module changing.
No rule content or threshold was added to `OpenInterestRules` — only this
bridging convention is documented.

## 10. What this module explicitly does not do

- No BUY/SELL signal generation.
- No scoring or weighting (`confidence_level` is about data sufficiency,
  not a trade-confidence score; `is_abnormal_spike` is a statistical
  outlier flag, not a trade trigger).
- No bullish/bearish interpretation of any computed value.
- No invented thresholds — `outlier_zscore_threshold`,
  `spike_zscore_threshold`, and `expected_interval` are unset
  placeholders; supply your own rule to enable that behavior.
- No GUI.

Waiting for approval before implementing the Premium & Discount Analysis
Module.
