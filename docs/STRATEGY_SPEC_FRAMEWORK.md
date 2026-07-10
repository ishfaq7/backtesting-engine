# Proprietary Strategy Specification Framework

Status: **Framework only. No trading rule, threshold, or scoring logic has
been implemented or assumed.** Every numeric/behavioral value in every
rule category is an explicit, unset placeholder until you supply it. This
document explains the design; `docs/strategy_spec.md` is the fill-in-the-
blank template; `config/strategy/` is the loadable form of the same thing.

## 1. Design principle: one generic primitive, reused everywhere

Rather than inventing a bespoke schema per rule category (which would mean
guessing what fields "Funding Rate Rules" or "Liquidity Rules" need), every
condition-based category is built from two generic primitives in
`btengine/strategy/rules/primitives.py`:

- **`RuleCondition`** — one atomic comparison: `<feature> <operator>
  <value>`. `feature`, `value` (and `value_high` for `BETWEEN`) have no
  default — they are `None`/empty until you supply them.
- **`RuleSet`** — a named, independently enable-able collection of
  conditions, plus how they combine (`ALL` / `ANY` / `CUSTOM`).

12 of the 16 requested modules (Funding Rate, Open Interest,
Premium/Discount, Liquidity, Market Structure, CVD, ATR, Entry, Exit, No
Trade, Session Filters, Market Condition Filters) are each a one-line
`class XRules(RuleSet): pass`-shaped subclass — distinct types for clarity
in the aggregate spec and validation messages, but structurally identical.
This is deliberate: it means "add a condition" is always the same
operation everywhere, and no category's schema secretly encodes an
assumption about what its rules should look like.

The remaining 4 don't fit the condition shape and are modeled differently,
honestly:

- **Risk Management** / **Position Management** — parameter containers
  (settings, not conditions). Every field defaults to `None`.
- **Trade Management** — action containers: a trigger `RuleCondition` paired
  with an open-ended `action: str | None` name and a free parameter map.
- **Scoring** — its own config (below); explicitly not a `RuleSet`.

## 2. Folder structure

```
src/btengine/strategy/
├── base.py                      (existing, untouched)
├── context.py                   (existing, untouched)
├── versioning.py                (existing, untouched)
├── profiles.py                  (existing, untouched)
├── spec.py                      NEW - StrategySpec (aggregates everything below)
├── spec_errors.py                NEW - StrategySpecError, SpecLoadError
├── spec_loader.py                 NEW - load_strategy_spec(root) from YAML
├── spec_validation.py             NEW - StrategySpecValidator
├── rules/
│   ├── primitives.py              RuleCondition, RuleSet, ComparisonOperator, RuleCombinationLogic
│   ├── funding_rate.py            FundingRateRules
│   ├── open_interest.py           OpenInterestRules
│   ├── premium_discount.py        PremiumDiscountRules
│   ├── liquidity.py                LiquidityRules
│   ├── market_structure.py        MarketStructureRules      (future support)
│   ├── cvd.py                     CVDRules                   (future support)
│   ├── atr.py                     ATRRules                    (future support)
│   ├── entry.py                   EntryRules
│   ├── exit.py                    ExitRules
│   ├── no_trade.py                NoTradeConditionRules
│   ├── session_filters.py         SessionFilterRules
│   ├── market_condition_filters.py MarketConditionFilterRules
│   ├── risk_management.py         RiskManagementRules        (parameters, not conditions)
│   ├── position_management.py     PositionManagementRules    (parameters, not conditions)
│   └── trade_management.py        TradeManagementRules, TradeManagementAction
└── scoring/
    └── config.py                  ScoringFactorConfig, ScoringModelConfig

config/strategy/                  NEW - the loadable, human-editable config
├── strategy.yaml                  name, version, profile, known_assumptions, todo
├── scoring.yaml                    ScoringModelConfig
└── rules/
    └── <15 files, one per rule category above>

docs/
├── strategy_spec.md               human-readable fill-in template
└── STRATEGY_SPEC_FRAMEWORK.md     this document
```

Nothing in `data/`, `backtest/`, `features/`, `feature_store/`,
`research/`, `integrations/`, or the existing `strategy/*.py` files was
touched — every addition above is a new file.

## 3. Scoring Model — config shape, no logic

Per the explicit instruction, the scoring *calculation* (how factors
combine into a number, what the number means) is not implemented anywhere.
`ScoringModelConfig` (`strategy/scoring/config.py`) only fixes what a
scoring configuration must express:

- **Multiple factors** — `factors: list[ScoringFactorConfig]`, each naming
  a source rule category and a weight.
- **Weighted scores** — `ScoringFactorConfig.weight` (no default, no
  assumed normalization scheme — this framework doesn't assume weights
  must sum to 1, or be positive, since that's itself a scoring-methodology
  choice).
- **Dynamic score calculation** — the config only names inputs; whatever
  later reads this config decides how to combine them.
- **Configurable thresholds** — `entry_threshold` / `exit_threshold`, both
  unset by default.
- **Versioning** — `version: str` has no default at all; every scoring
  config must be explicitly versioned (cross-reference with
  `strategy/versioning.py`'s `StrategyRegistry` for full-strategy version
  tracking).
- **Future AI scoring support** — `ai_scoring_enabled: bool = False` and
  `ai_model_name: str | None`, matching the `AIModelProvider` Protocol seam
  already defined in `btengine.integrations.ai_model`
  (`docs/RESEARCH_PLATFORM_ARCHITECTURE.md`). Turning this on requires a
  model name; nothing about what the model does is implied here.

## 4. Validation architecture

`StrategySpecValidator.validate(spec) -> list[SpecValidationIssue]`
(`strategy/spec_validation.py`) runs four families of checks, all
structural — never a judgment about whether a threshold is *reasonable*:

1. **Missing rules** — an enabled `RuleSet` with no conditions; an enabled
   condition missing `feature`/`value` (or `value_high` for `BETWEEN`); an
   enabled parameter container (Risk/Position Management) with an unset
   required field; enabled Trade Management with no actions, or an action
   missing its `action` name or trigger `feature`/`value`; enabled Scoring
   with no factors, or a factor missing `source_rule_set`/`weight`, or a
   missing threshold.
   **A disabled category is never flagged** — disabling something is a
   deliberate choice, not an incomplete one.
2. **Invalid configurations** — mostly caught earlier, at construction
   time, by each Pydantic model's own validators (e.g. `BETWEEN` needing
   `value_high > value`, risk percentages needing to be positive). The
   validator's remaining structural check here is that a Scoring factor's
   `source_rule_set` names one of the 15 known rule categories
   (`KNOWN_RULE_CATEGORIES`), catching a typo'd reference before it's
   silently ignored later.
3. **Conflicting rules** — for any `RuleSet` combining conditions with
   `ALL` logic, conditions on the *same* `feature` are checked for
   mathematically impossible combinations: contradictory `EQ` values,
   an `EQ` value outside its own `GT`/`LT`/`BETWEEN` bounds, matching
   `EQ`/`NEQ` values, or a lower bound at/above an upper bound (e.g. `x >
   10` and `x < 5` on the same feature can never both hold). This is pure
   interval arithmetic on the conditions' own stated values — never an
   opinion about what the feature means.
4. **Duplicate conditions** — duplicate condition names within one rule
   set (error), and conditions with identical
   `(feature, operator, value, value_high)` (warning — functionally
   redundant, not necessarily wrong). Same duplicate-name check for Trade
   Management action names and Scoring factor names.

## 5. Configuration loading

`load_strategy_spec(root)` (`strategy/spec_loader.py`) reads
`root/strategy.yaml`, `root/scoring.yaml`, and `root/rules/<category>.yaml`
for each of the 15 rule files, and assembles one `StrategySpec`. A missing
file is treated as "nothing configured yet" (empty mapping) — it's schema
validation (e.g. `scoring.version` having no default) that surfaces
genuinely missing information, not file presence. Running the loader
against the shipped `config/strategy/` template today produces a spec
whose only validation errors are the two required top-level fields
(`name`, `version`) — every rule category loads cleanly, disabled, exactly
as intended (verified by `tests/strategy/test_config_template.py`).

## 6. Integration flow with the Backtesting Engine

Nothing here changes how the engine calls a strategy — the seam is still
exactly `Strategy.on_market_event(context) -> Sequence[SignalEvent]`
(`docs/STRATEGY_AND_DATA_LAYER.md`). The flow, once a concrete strategy
plugin exists (not built yet):

```
config/strategy/*.yaml
        │  load_strategy_spec(...)
        ▼
   StrategySpec                       (this framework)
        │  StrategySpecValidator().validate(...) — fail fast if incomplete
        ▼
   [not yet built] a concrete Strategy plugin implementation that:
        - reads funding_rate_rules / open_interest_rules / premium_discount_rules /
          liquidity_rules to parametrize its analyzers (the actual
          feature-reading + comparison logic lives in the plugin, not here)
        - reads scoring to parametrize its (also not-yet-built) scoring
          calculation
        - reads entry_rules / no_trade_conditions / exit_rules /
          risk_management_rules / trade_management_rules /
          position_management_rules / session_filters /
          market_condition_filters to parametrize its policies
        │
        ▼
   Strategy.on_market_event(context: StrategyContext) -> list[SignalEvent]
        │  (StrategyContext/HistoryView from btengine.strategy.context - unchanged)
        ▼
   BacktestEngine (btengine.backtest.engine) - unchanged
        │  validates/executes signals exactly as it already does
        ▼
   BacktestResult
```

`market_structure_rules` / `cvd_rules` / `atr_rules` have no analyzer to
bind to yet (`btengine.features.market_structure/cvd/atr` are
interface-only stubs) — a plugin can reference these categories in its
config today, but they can't produce a real feature value until those
analyzers are implemented.

## 7. What's next (pending your input)

Everything below requires information only you can supply — this
framework deliberately stops here:

- Fill in `docs/strategy_spec.md`, then transcribe into `config/strategy/`.
- Run `StrategySpecValidator` and resolve every reported issue.
- Only then: implement the concrete `Strategy` plugin that reads this
  config and the scoring/analyzer calculations it depends on.
