"""Liquidity Rules — conditions over liquidation flow and long/short
positioning.

Feeds from :class:`~btengine.data.schema.Liquidation` /
:class:`~btengine.data.schema.LongShortRatio` via
``get_liquidations``, ``get_long_short_ratio``,
``get_top_long_short_account_ratio``, and
``get_top_long_short_position_ratio`` (see
``docs/COINGLASS_INTEGRATION.md`` §3, "Liquidity Analysis"). No condition
content is defined here — see ``docs/strategy_spec.md`` §Liquidity Rules
and ``config/strategy/rules/liquidity.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class LiquidityRules(RuleSet):
    """Conditions evaluated against liquidation/positioning-derived feature values."""
