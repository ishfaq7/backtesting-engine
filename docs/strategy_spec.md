# Strategy Specification — [STRATEGY NAME]

> **How to use this document.** This is the human-readable companion to
> the machine-loadable config in `config/strategy/` (schema:
> `btengine.strategy.spec.StrategySpec`, loader:
> `btengine.strategy.spec_loader.load_strategy_spec`). Fill in each section
> below in prose/table form first, then transcribe the final values into
> the matching YAML file. Every section starts empty/placeholder — nothing
> here was invented; run `StrategySpecValidator` after transcribing to
> confirm what's still missing.
>
> Every condition-based rule below uses the same generic shape (see
> `btengine/strategy/rules/primitives.py`):
> **Name | Feature | Operator (GT/GTE/LT/LTE/EQ/NEQ/BETWEEN) | Value | Value High (BETWEEN only) | Enabled | Description**

---

## Version History

| Version | Date | Author | Summary of changes |
|---|---|---|---|
| TODO | TODO | TODO | Initial draft |

---

## Known Assumptions

> Anything taken as given without independent verification. Not checked by
> the validator — this is a human record.

- TODO: e.g. "Funding rate is sourced from Binance only"
- TODO

---

## Funding Rules

**Data source:** CoinGlass funding rate (`get_funding_rate`,
`get_funding_rate_oi_weighted`) — see `docs/COINGLASS_INTEGRATION.md` §3.
**Config file:** `config/strategy/rules/funding_rate.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO — ALL | ANY | CUSTOM)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Open Interest Rules

**Data source:** CoinGlass open interest (`get_open_interest`,
`get_open_interest_aggregated`) — see `docs/COINGLASS_INTEGRATION.md` §3.
**Config file:** `config/strategy/rules/open_interest.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Premium/Discount Rules

**Data source:** perp-vs-index (or perp-vs-spot) price divergence,
computed from raw price history — see `docs/COINGLASS_INTEGRATION.md` §3.
**Config file:** `config/strategy/rules/premium_discount.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Liquidity Rules

**Data source:** CoinGlass liquidations and long/short positioning
(`get_liquidations`, `get_long_short_ratio`,
`get_top_long_short_account_ratio`, `get_top_long_short_position_ratio`) —
see `docs/COINGLASS_INTEGRATION.md` §3.
**Config file:** `config/strategy/rules/liquidity.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Entry Rules

Conditions that must hold to open a new position (typically evaluated
together with Scoring, below, and only once no No Trade Rule is
blocking).
**Config file:** `config/strategy/rules/entry.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Exit Rules

Conditions that close an open position outright (distinct from Trade
Management, which adjusts a still-open position).
**Config file:** `config/strategy/rules/exit.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Risk Rules

Strategy-level position sizing and exposure limits (proprietary — distinct
from the Core Backtesting Engine's own generic order sanity checks).
**Config file:** `config/strategy/rules/risk_management.yaml`

Enabled: `false` (TODO)

| Parameter | Value |
|---|---|
| Max risk per trade (%) | TODO |
| Max leverage | TODO |
| Max concurrent positions | TODO |
| Max daily loss (%) | TODO |
| Stop-loss type | TODO (e.g. FIXED_PCT, ATR_MULTIPLE — open, no default assumed) |

Notes: TODO

---

## No Trade Rules

A veto layer: if these conditions hold (per combination logic), the
strategy must not enter, regardless of score or Entry Rules.
**Config file:** `config/strategy/rules/no_trade.yaml`

Enabled: `false` (TODO)
Combination logic: `ALL` (TODO — decide deliberately: ANY = any single
condition vetoes; ALL = every listed condition must hold to veto)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

Notes: TODO

---

## Trade Management

Adjustments to an already-open position (trailing stops, partial exits,
breakeven moves) — distinct from Exit Rules, which close a position
outright. Each rule pairs a trigger condition with a named action.
**Config file:** `config/strategy/rules/trade_management.yaml`

Enabled: `false` (TODO)

| Action Name | Trigger Feature | Operator | Value | Action | Action Params | Enabled |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO (e.g. MOVE_STOP_TO_BREAKEVEN, PARTIAL_EXIT) | TODO | TODO |

Notes: TODO

---

## Position Management

How position size evolves over its lifetime (pyramiding, scale-ins,
netting behavior).
**Config file:** `config/strategy/rules/position_management.yaml`

Enabled: `false` (TODO)

| Parameter | Value |
|---|---|
| Allow pyramiding | TODO (true/false) |
| Max position scale-ins | TODO (required if pyramiding allowed) |
| Netting mode | TODO (e.g. NET, HEDGE — open, no default assumed) |

Notes: TODO

---

## Scoring

Multi-factor, weighted, versioned scoring configuration. **No scoring
logic is defined here or implemented anywhere in the codebase yet** — this
section only records the intended factors/weights/thresholds.
**Config file:** `config/strategy/scoring.yaml`

Version: TODO (required, e.g. "0.1.0")
Enabled: `false` (TODO)

| Factor Name | Source Rule Category | Weight | Enabled |
|---|---|---|---|
| TODO | TODO (must match a rule category above) | TODO | TODO |

| Threshold | Value |
|---|---|
| Entry threshold | TODO |
| Exit threshold | TODO |

Future AI scoring: disabled (`ai_scoring_enabled: false`) until a concrete
model integration exists (see `btengine.integrations.ai_model`).

Notes: TODO

---

## Market Filters

Covers Session Filters, Market Condition Filters, and the three
future-support analyzer categories (Market Structure, CVD, ATR) — none of
which have condition content or, for the latter three, an implemented
analyzer yet.

### Session Filters
**Config file:** `config/strategy/rules/session_filters.yaml`

Enabled: `false` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO (e.g. hour_of_day_utc, day_of_week) | TODO | TODO | | TODO | TODO |

### Market Condition Filters
**Config file:** `config/strategy/rules/market_condition_filters.yaml`

Enabled: `false` (TODO)

| Name | Feature | Operator | Value | Value High | Enabled | Description |
|---|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | | TODO | TODO |

### Market Structure Rules — future support
`config/strategy/rules/market_structure.yaml` — no conditions possible
until `MarketStructureAnalyzer` (`btengine.features.market_structure`) is
implemented.

### CVD Rules — future support
`config/strategy/rules/cvd.yaml` — no conditions possible until
`CVDAnalyzer` (`btengine.features.cvd`) and its taker buy/sell volume data
source are implemented.

### ATR Rules — future support
`config/strategy/rules/atr.yaml` — no conditions possible until
`ATRAnalyzer` (`btengine.features.atr`) is implemented.

---

## TODO List

- [ ] Set strategy `name` and `version` (`config/strategy/strategy.yaml`)
- [ ] Define Funding Rate Rules
- [ ] Define Open Interest Rules
- [ ] Define Premium/Discount Rules
- [ ] Define Liquidity Rules
- [ ] Define Entry Rules
- [ ] Define Exit Rules
- [ ] Define Risk Rules
- [ ] Define No Trade Rules
- [ ] Define Trade Management actions
- [ ] Define Position Management parameters
- [ ] Define Scoring factors, weights, version, and thresholds
- [ ] Define Session Filters
- [ ] Define Market Condition Filters
- [ ] Run `StrategySpecValidator` and resolve every reported issue
- [ ] Confirm liquidation field names against a live CoinGlass API key
      (see `docs/COINGLASS_INTEGRATION.md`)
