"""ATR Rules — future support.

Would feed from :class:`~btengine.features.atr.ATRAnalyzer`, which is an
interface-only stub (``raise NotImplementedError``) as of
``docs/RESEARCH_PLATFORM_ARCHITECTURE.md`` — no ATR/volatility value
exists yet to condition on. This module only reserves the config shape.
No condition content is defined here — see ``docs/strategy_spec.md``
§Market Filters and ``config/strategy/rules/atr.yaml``.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class ATRRules(RuleSet):
    """Conditions evaluated against ATR-derived feature values (future
    support — the underlying analyzer is not yet implemented)."""
