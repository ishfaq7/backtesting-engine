"""Market Condition Filters — conditions gating broader market regime
(e.g. volatility regime, trend regime) before trading is permitted.

Distinct from Session Filters (time-based) and No Trade Conditions
(event/state-based veto) — this category is regime-based, and will likely
draw on the Market Structure/ATR analyzers once implemented (see
:mod:`~btengine.strategy.rules.market_structure`,
:mod:`~btengine.strategy.rules.atr`). No condition content is defined
here — see ``docs/strategy_spec.md`` §Market Filters and
``config/strategy/rules/market_condition_filters.yaml`` for the loadable
form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class MarketConditionFilterRules(RuleSet):
    """Conditions that gate trading based on overall market regime."""
