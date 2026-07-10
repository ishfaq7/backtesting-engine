"""Open Interest Rules — conditions over CoinGlass open-interest data.

Feeds from :class:`~btengine.data.schema.OpenInterest` /
``CoinGlassDataProvider.get_open_interest`` /
``get_open_interest_aggregated`` (see ``docs/COINGLASS_INTEGRATION.md``
§3, "Open Interest Analysis"). No condition content is defined here — see
``docs/strategy_spec.md`` §Open Interest Rules for the owner-supplied
rules and ``config/strategy/rules/open_interest.yaml`` for the loadable
form.
"""

from __future__ import annotations

from btengine.strategy.rules.primitives import RuleSet


class OpenInterestRules(RuleSet):
    """Conditions evaluated against open-interest-derived feature values."""
