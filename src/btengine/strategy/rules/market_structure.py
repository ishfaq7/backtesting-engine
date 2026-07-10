"""Market Structure Rules — future support.

Would feed from :class:`~btengine.features.market_structure.MarketStructureAnalyzer`,
which is an interface-only stub (``raise NotImplementedError``) as of
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` — no market-structure
classification exists yet to condition on. This module only reserves the
config shape so a spec can reference "market structure rules" today and
have real analyzer output to bind to later, without a schema migration.
No condition content is defined here — see ``docs/strategy_spec.md``
§Market Filters and ``config/strategy/rules/market_structure.yaml``.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class MarketStructureRules(RuleSet):
    """Conditions evaluated against market-structure-derived feature values
    (future support — the underlying analyzer is not yet implemented)."""
