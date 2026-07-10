"""Session Filters — conditions gating *when* trading is allowed
(time-of-day, day-of-week, specific date exclusions).

Uses the same generic :class:`~btengine.strategy.rules.primitives.RuleCondition`
shape as every other rule category — e.g. a condition with
``feature="hour_of_day_utc"`` — rather than a bespoke time-window schema,
so no assumption about session boundaries (which hours, which days) is
made here. No condition content is defined here — see
``docs/strategy_spec.md`` §Market Filters and
``config/strategy/rules/session_filters.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class SessionFilterRules(RuleSet):
    """Conditions that gate which sessions/times trading is permitted."""
