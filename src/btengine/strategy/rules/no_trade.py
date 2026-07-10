"""No Trade Conditions — conditions that block entry regardless of score.

Logically a veto layer: if any enabled condition here holds (under its
``combination_logic``), the strategy must not enter, no matter what the
Scoring Model or Entry Rules say. No condition content is defined here —
see ``docs/strategy_spec.md`` §No Trade Rules and
``config/strategy/rules/no_trade.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class NoTradeConditionRules(RuleSet):
    """Conditions that veto entry regardless of score/Entry Rules."""
