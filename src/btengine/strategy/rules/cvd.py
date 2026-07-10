"""CVD Rules — future support.

Would feed from :class:`~btengine.features.cvd.CVDAnalyzer`, which is an
interface-only stub (``raise NotImplementedError``) as of
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` — CVD also needs taker
buy/sell volume data not yet wired into the data layer (see
``docs/COINGLASS_INTEGRATION.md``, "Additional data likely needed
later"). This module only reserves the config shape. No condition content
is defined here — see ``docs/strategy_spec.md`` §Market Filters and
``config/strategy/rules/cvd.yaml``.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class CVDRules(RuleSet):
    """Conditions evaluated against CVD-derived feature values (future
    support — the underlying analyzer and its data source are not yet
    implemented)."""
