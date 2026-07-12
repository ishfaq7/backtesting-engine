# Signal Validation Engine

Status: **Validation only. No BUY/SELL signal, proprietary strategy
rule, risk management, or trade management has been implemented or
assumed.** This engine sits between the Scoring Engine and the
not-yet-built Decision Engine and does exactly one job: check the
quality and integrity of a `StrategyScore` and its four upstream
analyses, and report what it found. **It never modifies a score** — it
only reads one and returns it unchanged, embedded in its own diagnostic
output.

Unlike the Scoring Engine's providers (explicitly forbidden from
containing real formulas, since that's proprietary strategy content),
every check in this engine is fully implemented and working — this task
asks for "a production-grade validation layer," and data-quality
validation (missing/invalid/duplicate/stale/inconsistent) is generic
engineering, not a trading rule.

## 1. Folder structure

```
src/btengine/signal_validation/
├── __init__.py
├── errors.py                SignalValidationError, SignalValidationConfigError
├── models.py                  SignalValidationIssue, ConfidenceStatus, ModuleHealthStatus,
│                                DataIntegrityStatus, FeatureCompleteness, ValidatedStrategyState
├── config.py                    SignalValidationConfig, load_signal_validation_config()
├── context.py                     ValidationContext
├── checks/
│   ├── __init__.py
│   ├── base.py                     ValidationCheck (ABC, the "Validation interfaces" deliverable)
│   └── builtin.py                    8 concrete, fully-implemented checks + default_checks()
└── engine.py                          SignalValidationEngine (the orchestrator)

tests/signal_validation/    one test file per module above (+ conftest.py fixtures), 100% coverage
config/signal_validation/
└── signal_validation.yaml    placeholder template (mirrors config/scoring/scoring_engine.yaml's convention)
```

Named `btengine.signal_validation` (not `btengine.validation`) to avoid
colliding with the already-existing, unrelated `btengine.data.validation`
module. Nothing in `btengine.strategy`, `btengine.features`,
`btengine.data`, `btengine.backtest`, `btengine.analysis.*`, or
`btengine.scoring` was modified. Like `btengine.scoring`, this package
intentionally depends on the analysis modules and on `btengine.scoring`
— correct layering, since it sits one level above the Scoring Engine.

## 2. Input

```python
def validate(
    self, symbol: str, reference_time: datetime, *,
    score: StrategyScore,
    funding: FundingAnalysis | None = None,
    open_interest: OpenInterestAnalysis | None = None,
    premium_discount: PremiumDiscountAnalysis | None = None,
    liquidity: LiquidityAnalysis | None = None,
) -> ValidatedStrategyState
```

`score` is required; the four analyses are optional (a missing one is
itself something this engine validates — see §4). `reference_time` is
supplied by the caller and never read from the wall clock internally, so
this engine behaves identically live or replayed inside a backtest
against a `SimulationClock`.

## 3. Interfaces (Python classes)

### `ValidationCheck` (`checks/base.py`)

```python
class ValidationCheck(ABC):
    @property
    @abstractmethod
    def check_name(self) -> str: ...
    @abstractmethod
    def run(self, context: ValidationContext) -> list[SignalValidationIssue]: ...
```

One independent, stateless rule per class. This is the extension seam
for every capability listed under FUTURE SUPPORT — see §7.

### `ValidationContext` (`context.py`)

```python
@dataclass(frozen=True)
class ValidationContext:
    symbol: str
    reference_time: datetime
    score: StrategyScore
    funding: FundingAnalysis | None
    open_interest: OpenInterestAnalysis | None
    premium_discount: PremiumDiscountAnalysis | None
    liquidity: LiquidityAnalysis | None
    config: SignalValidationConfig
```

Everything one check needs, bundled — the same Interface Segregation
role `ScoreComponent`/`CandleObservation` play for their own layers.

### `SignalValidationEngine` (`engine.py`)

```python
class SignalValidationEngine:
    def __init__(
        self, config: SignalValidationConfig, *, checks: list[ValidationCheck] | None = None
    ) -> None: ...
    def validate(self, symbol, reference_time, *, score, funding=None, ...) -> ValidatedStrategyState: ...
```

Dependency injection: `checks` defaults to
`checks.builtin.default_checks()` but any list of `ValidationCheck`
instances can be substituted, standard SOLID Dependency Inversion.

## 4. The ten responsibilities → checks

Eight are stateless, pluggable `ValidationCheck` classes (`checks/builtin.py`).
Two need memory across calls and live directly on `SignalValidationEngine`.

| # | Responsibility | Where | Definition |
|---|---|---|---|
| 1 | Missing feature inputs | `MissingFeatureInputsCheck` | Flags (`WARNING`) any of the four analyses not supplied at all |
| 2 | Invalid analytical objects | `InvalidAnalyticalObjectsCheck` | Flags (`ERROR`) an empty `symbol`, a naive timestamp, or an out-of-range/NaN `confidence_level` on any supplied analysis — defense-in-depth re-validation of plain (non-pydantic) dataclasses |
| 3 | Missing score providers | `MissingScoreProvidersCheck` | Any `score.feature_status[name] != AVAILABLE` — `ERROR` if `name` is in `required_providers`, else `WARNING` |
| 4 | Duplicate signals | engine (`_check_duplicate_signal`) | Same `(symbol, score.as_of, score.score_version)` seen before by this engine instance — `WARNING` |
| 5 | Conflicting module outputs | `ConflictingModuleOutputsCheck` | Scoped to *identity* consistency only: symbol mismatch (`ERROR`) and, if `max_timestamp_skew` is configured, timestamp divergence beyond it (`WARNING`) — deliberately **not** a comparison of analytical field values, which would be a strategy interpretation |
| 6 | Invalid confidence values | `InvalidConfidenceValuesCheck` | `score.confidence` NaN/infinite/out-of-range → `ERROR`; below configured `min_confidence` → `WARNING` |
| 7 | Version mismatches | `VersionMismatchCheck` | `score.score_version` vs. configured `expected_score_version` (`WARNING`), plus disagreement between the score's own components' `provider_version`s (`WARNING`) |
| 8 | Data freshness | `DataFreshnessCheck` | A timestamp from the future relative to `reference_time` is always flagged (`WARNING`); staleness beyond configured `max_staleness` is flagged (`WARNING`) |
| 9 | Historical consistency | engine (`_check_historical_consistency`) | Per-symbol bounded history (size `history_window`) of previously validated `as_of` timestamps; a new one that isn't strictly after the last recorded one is out-of-order replay — `ERROR` |
| 10 | Strategy completeness | `StrategyCompletenessCheck` | Aggregate available/total provider ratio below configured `min_completeness_ratio` — `WARNING` (distinct from #3, which flags individual providers by name) |

Checks #4 and #9 need cross-call memory (a duplicate-signal ledger, a
per-symbol timestamp history) that a stateless `ValidationCheck` cannot
hold, so they're engine-native rather than pluggable — the same split
`ScoringEngine` uses for its own duplicate-calculation detection.

## 5. `ValidatedStrategyState` — the output object

```python
@dataclass(frozen=True)
class ValidatedStrategyState:
    symbol: str
    as_of: datetime
    strategy_version: str

    score: StrategyScore                      # unmodified pass-through

    validation_passed: bool                     # False iff any ERROR-severity issue
    validation_errors: tuple[SignalValidationIssue, ...]
    validation_warnings: tuple[SignalValidationIssue, ...]

    confidence_status: ConfidenceStatus          # VALID | LOW | INVALID | UNKNOWN
    feature_completeness: FeatureCompleteness
    module_health: dict[str, ModuleHealthStatus]   # HEALTHY | MISSING | NOT_IMPLEMENTED | INVALID | STALE
    data_integrity: DataIntegrityStatus              # VALID | STALE | INCONSISTENT | INVALID
```

`data_integrity` is a prioritized rollup: `STALE` if any freshness issue
exists at all (most actionable), else `INCONSISTENT` if any
consistency/structural/sequencing `ERROR` exists, else `INVALID` for any
other `ERROR`, else `VALID`. `feature_completeness.is_sufficient` stays
`None` (unclassified) until `min_completeness_ratio` is configured —
`completeness_ratio` itself is always computed.

## 6. Configuration

```python
@dataclass(frozen=True)
class SignalValidationConfig:
    engine_version: str                                    # required, no default

    expected_score_version: str | None = None
    max_staleness: timedelta | None = None
    max_timestamp_skew: timedelta | None = None
    min_confidence: float | None = None
    min_completeness_ratio: float | None = None
    required_providers: tuple[str, ...] | None = None
    history_window: int = 20
```

Every threshold-shaped field defaults to `None` — an explicit,
unset placeholder, exactly like every upstream analysis/scoring config.
`history_window` is the one generic technical parameter (a buffer size)
with a sensible default, the same category as an SMA period elsewhere in
this codebase. `load_signal_validation_config(path)` loads
`config/signal_validation/signal_validation.yaml`, following the same
"missing key is a placeholder, not an error; only schema validation
surfaces genuinely missing information" convention as
`load_strategy_spec`/`load_scoring_engine_config`.

## 7. Future extension points

None of the six capabilities below have a concrete integration — no
stub classes were added, since a stub with nothing to plug into is
hollow scaffolding. Each is architecturally ready today:

- **AI Validation** — implement `ValidationCheck.run()` wrapping an
  `btengine.integrations.ai_model.AIModelProvider` (already built) to
  flag anomalies an ML model detects; add it to the `checks` list passed
  into `SignalValidationEngine`. No engine change required.
- **Ensemble Validation** — a `ValidationCheck` that itself runs several
  other checks (or several `AIModelProvider`s) and reconciles their
  verdicts; still just one more item in the `checks` list, since nothing
  prevents a check from being a composite of other checks.
- **Rule Conflict Detection** — once the Strategy Specification
  Framework's `RuleCondition`/`RuleSet` primitives have a real evaluator
  (referenced but not yet built — see the analysis modules'
  `to_feature_map()` docs), a `ValidationCheck` can inspect which rules
  fired and flag contradictory ones. `ConflictingModuleOutputsCheck`
  deliberately stayed at the identity/timestamp level rather than
  reaching into rule evaluation, precisely so this extension has a clean
  seam to land in later.
- **Cross-Timeframe Validation** — mirrors
  `PremiumDiscountAnalysisEngine`'s `timeframe_label` pattern: run
  `SignalValidationEngine.validate()` once per timeframe (or write a
  `ValidationCheck` that reads `PremiumDiscountAnalysis.timeframe`
  directly) and reconcile at a higher level.
- **Multi-Coin Validation** / **Portfolio Validation** — `validate()` is
  already symbol-scoped, and its only cross-call state (the
  duplicate-signal ledger, the historical-consistency history) is keyed
  by `symbol`, so it never leaks across coins. A future
  `PortfolioValidator` would loop over symbols, collect
  `ValidatedStrategyState`s, and apply its own portfolio-level
  reconciliation — a new, higher-level component, not a change to this
  one.

## 8. What this engine explicitly does not do

- No BUY/SELL signal generation.
- No proprietary strategy rules.
- No Risk Management.
- No Trade Management.
- Never modifies a `StrategyScore` — every `validate()` call returns the
  exact object it was given, embedded unchanged in `ValidatedStrategyState.score`.
- No GUI.

Waiting for approval before implementing the Decision Engine.
