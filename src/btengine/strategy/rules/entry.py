"""Entry Rules — conditions that must hold for the strategy to open a
new position.

Typically evaluated together with the Scoring Model
(``docs/strategy_spec.md`` §Scoring) and after confirming no
:class:`~btengine.strategy.rules.no_trade.NoTradeConditionRules` are
blocking. No condition content is defined here — see
``docs/strategy_spec.md`` §Entry Rules and
``config/strategy/rules/entry.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class EntryRules(RuleSet):
    """Conditions that gate opening a new position."""
