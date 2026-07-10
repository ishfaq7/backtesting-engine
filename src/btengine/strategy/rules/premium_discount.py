"""Premium/Discount Rules — conditions over perp-vs-index (or perp-vs-spot)
price divergence.

Feeds from :class:`~btengine.data.schema.Candle` price series across
instruments (see ``docs/COINGLASS_INTEGRATION.md`` §3, "Premium/Discount
Analysis" — the raw price data this integration provides is the input;
the premium/discount calculation itself is owner-supplied, not defined
here). No condition content is defined here — see ``docs/strategy_spec.md``
§Premium/Discount Rules and
``config/strategy/rules/premium_discount.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class PremiumDiscountRules(RuleSet):
    """Conditions evaluated against premium/discount-derived feature values."""
