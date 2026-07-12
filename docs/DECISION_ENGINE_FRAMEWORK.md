# Decision Engine Framework

Status: **Framework only. No BUY/SELL rule, Entry Rule, Exit Rule, Risk
Rule, or proprietary decision logic has been implemented or assumed.**
This is explicitly part of "the proprietary trading system" per the task
that requested it. `DecisionStatus` and every other field in this
module describe *where a signal sits in the decision pipeline* — never
a trading action. No BUY/SELL/ENTER/EXIT vocabulary appears anywhere in
this codebase's `btengine.decision` package; `tests/decision/test_models.py`
asserts this directly.

## 1. Folder structure

```
src/btengine/decision/
├── __init__.py
├── errors.py                DecisionEngineError, DecisionEngineConfigError
├── models.py                  DecisionStatus, DecisionOutcome, DecisionValidationIssue, DecisionContext
├── config.py                    DecisionEngineConfig, order_provider_names_by_priority(),
│                                  load_decision_engine_config()
├── context.py                     DecisionRequest
├── providers/
│   ├── __init__.py
│   └── base.py                     DecisionProvider (ABC) — zero concrete implementations
├── checks/
│   ├── __init__.py
│   ├── base.py                       DecisionValidationCheck (ABC)
│   └── builtin.py                      5 concrete, real checks + default_checks()
└── engine.py                             DecisionEngine (the orchestrator)

tests/decision/       one test file per module above (+ conftest.py fixtures), 100% coverage
config/decision/
└── decision_engine.yaml   placeholder template (mirrors config/signal_validation's convention)
```

Nothing in `btengine.strategy`, `btengine.features`, `btengine.data`,
`btengine.backtest`, `btengine.analysis.*`, `btengine.scoring`, or
`btengine.signal_validation` was modified. `btengine.decision` sits one
layer above `btengine.signal_validation`, the same intentional,
correct-layering dependency pattern `btengine.scoring` and
`btengine.signal_validation` already established.

## 2. Input

```python
def decide(
    self, symbol: str, reference_time: datetime, *,
    validated_state: ValidatedStrategyState,
    funding: FundingAnalysis | None = None,
    open_interest: OpenInterestAnalysis | None = None,
    premium_discount: PremiumDiscountAnalysis | None = None,
    liquidity: LiquidityAnalysis | None = None,
) -> DecisionContext
```

`validated_state` is required; the four analyses are optional (a
missing one is itself validated — see §5). The upstream
`StrategyScore` — the task's other named input — is reached via
`validated_state.score` rather than a separate parameter: there is
exactly one source of truth, so the score and the state it was
validated as part of can never disagree by construction. `reference_time`
is supplied by the caller and never read from the wall clock, so this
engine behaves identically live or replayed inside a backtest.

## 3. Interfaces (Python classes)

### `DecisionProvider` (`providers/base.py`)

```python
class DecisionProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...
    @property
    @abstractmethod
    def provider_version(self) -> str: ...
    @abstractmethod
    def decide(self, request: DecisionRequest) -> DecisionOutcome: ...
```

**Zero concrete implementations ship in this package.** Every prior
framework in this project (Scoring Engine) shipped one concrete-but-
`NotImplementedError` provider per *known, fixed* analyzer (funding,
open interest, ...). There is no equivalent fixed enumeration of
"decision providers" — "Rule-based," "AI," and "Ensemble" are all
future, strategy-owner-defined content (see §7), not generic
infrastructure this framework can demonstrate with a placeholder class.
Tests exercise this interface with disposable test-double providers.

"Support configurable rule execution" is satisfied by this interface
being pluggable (dependency injection into `DecisionEngine`) and by
`DecisionEngineConfig.provider_priorities` controlling evaluation
order — deliberately **not** by a second, separate "rule" interface
layered on top: a future Rule-based Decision Engine simply *is* one
`DecisionProvider` implementation that happens to run configured rules
internally, so no redundant scaffolding was added for that distinction.

### `DecisionValidationCheck` (`checks/base.py`)

```python
class DecisionValidationCheck(ABC):
    @property
    @abstractmethod
    def check_name(self) -> str: ...
    @abstractmethod
    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]: ...
```

Structurally the same shape as
`btengine.signal_validation.checks.base.ValidationCheck`, defined fresh
rather than shared — the same "each validation layer owns its own
issue/check vocabulary" convention used by every validator built so far
in this project. Five checks ship, fully implemented (see §5) — unlike
`DecisionProvider`, data-quality validation is generic engineering, not
proprietary strategy content, so it's built for real here exactly as it
was in the Signal Validation Engine.

### `DecisionRequest` (`context.py`)

The input bundle every check/provider receives — not to be confused
with `DecisionContext` (the *output*, named literally per this task's
spec). Bundles `symbol`, `reference_time`, `validated_state`, the four
analyses, `config`, and `provider_names` (the names of every registered
provider, for the "unsupported decision providers" check).

### `DecisionEngine` (`engine.py`)

```python
class DecisionEngine:
    def __init__(
        self, config: DecisionEngineConfig, *,
        providers: list[DecisionProvider] | None = None,
        checks: list[DecisionValidationCheck] | None = None,
    ) -> None: ...
    def decide(self, symbol, reference_time, *, validated_state, funding=None, ...) -> DecisionContext: ...
```

Dependency injection throughout: `checks` defaults to
`checks.builtin.default_checks()`, `providers` defaults to an empty
list (the expected state today). **Never calls CoinGlass, the Feature
Store, the Scoring Engine, or the Signal Validation Engine directly** —
it only accepts already-prepared objects, the same boundary discipline
every engine in this project observes.

## 4. `DecisionContext` — the output object

```python
@dataclass(frozen=True)
class DecisionContext:
    symbol: str
    as_of: datetime
    strategy_version: str
    timestamp: datetime                          # when this context was prepared (reference_time)

    decision_status: DecisionStatus                # NOT_READY | PENDING | EVALUATED
    decision_reason: str
    validation_status: ValidationStatus              # reused from btengine.scoring.models
    execution_ready: bool

    provider_outcomes: tuple[DecisionOutcome, ...] = ()
    validation_errors: tuple[DecisionValidationIssue, ...] = ()
    validation_warnings: tuple[DecisionValidationIssue, ...] = ()
    metadata: dict[str, object] = {}
```

`DecisionStatus` has exactly three values, describing pipeline
position, never a trading action:

- **`NOT_READY`** — input validation failed, or
  `ValidatedStrategyState.validation_passed` is `False` and
  `require_validation_passed` is set (the default).
- **`PENDING`** — input is valid but no decision provider produced a
  substantive outcome — **the state every call resolves to today**,
  since this framework ships zero decision logic.
- **`EVALUATED`** — a framework hook for when a real provider exists;
  unreachable by anything shipped in this task.

`execution_ready` is a purely structural gate
(`decision_status is EVALUATED and no validation errors`) — it never
encodes an opinion about what should be executed, and is `False` for
every call today by construction (asserted directly in tests).

## 5. Validation — six named responsibilities

Five are stateless, pluggable `DecisionValidationCheck` classes. One
needs cross-call memory and lives directly on `DecisionEngine`.

| Responsibility | Where | Definition |
|---|---|---|
| Missing inputs | `MissingInputsCheck` | Flags (`WARNING`) any of the four analyses not supplied |
| Invalid score objects | `InvalidScoreObjectCheck` | Flags (`ERROR`) `validated_state.score` having an empty symbol, a naive timestamp, an empty `score_version`, or an out-of-range/NaN `confidence` |
| Invalid analysis objects | `InvalidAnalysisObjectsCheck` | Same structural checks (empty symbol, naive timestamp, invalid `confidence_level`) reapplied to every supplied analysis — deliberate defense-in-depth, mirroring `btengine.signal_validation.checks.builtin.InvalidAnalyticalObjectsCheck` at this later stage rather than only trusting the prior layer's verdict |
| Strategy version mismatch | `StrategyVersionMismatchCheck` | `validated_state.strategy_version` vs. configured `expected_strategy_version` (`WARNING`), plus internal disagreement between `strategy_version` and its own embedded `score.score_version` (`WARNING`) |
| Unsupported decision providers | `UnsupportedDecisionProvidersCheck` | Any name in `required_providers` not actually registered with the engine (`ERROR`) |
| Duplicate processing | engine (`_check_duplicate_processing`) | Same `(symbol, validated_state.as_of, strategy_version)` already processed by this engine instance (`WARNING`) — the same per-symbol ledger pattern `ScoringEngine`/`SignalValidationEngine` use for their own duplicate detection |

## 6. Configuration

```python
@dataclass(frozen=True)
class DecisionEngineConfig:
    engine_version: str                              # required, no default

    expected_strategy_version: str | None = None
    required_providers: tuple[str, ...] | None = None
    provider_priorities: dict[str, int] = {}
    require_validation_passed: bool = True
    history_window: int = 20
```

Every strategy-shaped field defaults to `None`/empty — an explicit
placeholder, exactly like every upstream config. `require_validation_passed`
(default `True`) and `history_window` (default `20`) are the two fields
with a real default: the former is an operational safety switch ("don't
hand unvalidated data downstream"), not a trading rule; the latter is a
generic technical buffer size, the same category as an SMA period
elsewhere in this codebase. `load_decision_engine_config(path)` loads
`config/decision/decision_engine.yaml`, following the "missing key is a
placeholder, not an error" convention every prior loader in this
project uses.

## 7. Integration flow

```mermaid
flowchart LR
    subgraph Upstream["Already built"]
        SE[ScoringEngine] -->|StrategyScore| SVE[SignalValidationEngine]
        SVE -->|ValidatedStrategyState\n(embeds StrategyScore)| DE
        FA[FundingAnalysis]
        OA[OpenInterestAnalysis]
        PA[PremiumDiscountAnalysis]
        LA[LiquidityAnalysis]
    end

    subgraph DecisionPkg["btengine.decision"]
        DE[DecisionEngine]
        CHK[DecisionValidationCheck x5]
        PROV["DecisionProvider list\n(empty today)"]
        CFG[DecisionEngineConfig]
        OUT[DecisionContext]
    end

    FA --> DE
    OA --> DE
    PA --> DE
    LA --> DE
    CFG --> DE

    DE --> CHK
    DE --> PROV
    DE --> OUT

    OUT -.future.-> EXEC["Trade Execution / Order Management\n(not yet built, requires\nproprietary decision rules)"]
```

`DecisionEngine` never reaches upstream past `ValidatedStrategyState`
and the four analyses — it does not call the Scoring Engine, the Signal
Validation Engine, CoinGlass, or any data source directly.

## 8. Future extension points

None of the six capabilities below have a concrete implementation — no
stub classes were added, since a stub with nothing to plug into is
hollow scaffolding. Each is architecturally ready today:

- **Rule-based Decision Engine** — implement `DecisionProvider.decide()`
  evaluating the strategy owner's actual entry/exit/risk rules (once
  supplied) and inject it via `DecisionEngine(config, providers=[...])`.
  No engine change required.
- **AI Decision Engine** — implement `DecisionProvider.decide()`
  wrapping `btengine.integrations.ai_model.AIModelProvider` (already
  built, in the Research Platform Architecture phase), the same seam
  the Scoring Engine's own AI extension point documents.
- **Ensemble Decision Models** — a `DecisionProvider` that itself calls
  several other `DecisionProvider`s (or several `AIModelProvider`s) and
  reconciles their outcomes; still just one more item in the
  `providers` list.
- **Multi-Timeframe Decisions** — mirrors
  `PremiumDiscountAnalysisEngine`'s `timeframe_label` pattern: run
  `DecisionEngine.decide()` once per timeframe (or write a
  `DecisionProvider` that reads `PremiumDiscountAnalysis.timeframe`
  directly) and reconcile at a higher level.
- **Multi-Coin Decisions** / **Portfolio-Level Decisions** — `decide()`
  is already symbol-scoped, and its only cross-call state (the
  duplicate-processing ledger) is keyed by `symbol`, so it never leaks
  across coins. A future `PortfolioDecisionEngine` would loop over
  symbols, collect `DecisionContext`s, and apply its own
  portfolio-level reconciliation — a new, higher-level component, not a
  change to this one.

## 9. What this framework explicitly does not do

- No BUY/SELL/ENTER/EXIT rule of any kind.
- No Risk Rules.
- No trading signal generated from assumptions.
- No concrete `DecisionProvider` implementation.
- No GUI.

Waiting for approval before implementing proprietary decision rules.
