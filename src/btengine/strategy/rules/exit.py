"""Exit Rules — conditions that trigger closing an open position.

Distinct from :class:`~btengine.strategy.rules.trade_management.TradeManagementRules`,
which adjusts a still-open position (trailing stops, partial exits)
rather than closing it outright. No condition content is defined here —
see ``docs/strategy_spec.md`` §Exit Rules and
``config/strategy/rules/exit.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class ExitRules(RuleSet):
    """Conditions that gate closing an open position."""
