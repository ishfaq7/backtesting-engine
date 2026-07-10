"""Funding Rate Rules — conditions over CoinGlass funding-rate data.

Feeds from :class:`~btengine.data.schema.FundingRate` /
``CoinGlassDataProvider.get_funding_rate`` /
``get_funding_rate_oi_weighted`` (see ``docs/COINGLASS_INTEGRATION.md``
§3, "Funding Rate Analysis"). No condition content is defined here — see
``docs/strategy_spec.md`` §Funding Rules for the owner-supplied rules and
``config/strategy/rules/funding_rate.yaml`` for the loadable form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class FundingRateRules(RuleSet):
    """Conditions evaluated against funding-rate-derived feature values."""
