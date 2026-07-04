"""Enforces the CoinGlass **Startup** plan's interval and history-length limits.

Source: CoinGlass's published plan comparison (coinglass.com/pricing) and the
official per-endpoint-category "plans-interval-history-length" references in
https://github.com/coinglass-official/coinglass-api-skills, as of this
writing. Re-confirm against the account's live plan/dashboard if CoinGlass
changes its tiers or the subscription is upgraded — this module is the one
place that would need updating.

The Startup plan grants:

- Intervals: 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d (no 1m/5m/15m — Standard+ only;
  1w is not offered as an interval on any plan for these endpoints).
- Maximum history length, per interval: shorter intervals get less
  lookback; only 1d is granted "all-time" (since the instrument's listing).

This module is scoped to a single, known, fixed plan deliberately: there is
one paying account and one plan, so a generic multi-tier configuration
system would be speculative complexity with no present use.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from btengine.data.errors import PlanRestrictionError
from btengine.data.schema import Timeframe

PLAN_NAME = "startup"

_MAX_HISTORY_BY_TIMEFRAME: dict[Timeframe, timedelta | None] = {
    Timeframe.MIN_30: timedelta(days=90),
    Timeframe.HOUR_1: timedelta(days=180),
    Timeframe.HOUR_2: timedelta(days=180),
    Timeframe.HOUR_4: timedelta(days=180),
    Timeframe.HOUR_6: timedelta(days=360),
    Timeframe.HOUR_8: timedelta(days=360),
    Timeframe.HOUR_12: timedelta(days=360),
    Timeframe.DAY_1: None,  # "all-time" (since the instrument's listing)
}


def is_timeframe_supported(timeframe: Timeframe) -> bool:
    return timeframe in _MAX_HISTORY_BY_TIMEFRAME


def max_history(timeframe: Timeframe) -> timedelta | None:
    """Maximum lookback the Startup plan grants for ``timeframe``, or
    ``None`` if it's unbounded ("all-time")."""
    return _MAX_HISTORY_BY_TIMEFRAME.get(timeframe)


def validate_request(timeframe: Timeframe, start: datetime, end: datetime) -> None:
    """Raise :class:`PlanRestrictionError` if this request exceeds what the
    Startup plan grants. Called before any HTTP request is issued.
    """
    if not is_timeframe_supported(timeframe):
        raise PlanRestrictionError(
            f"The {PLAN_NAME} plan does not support the {timeframe.value} interval "
            f"for this endpoint category (supported: "
            f"{', '.join(tf.value for tf in _MAX_HISTORY_BY_TIMEFRAME)})",
            plan=PLAN_NAME,
            context={"timeframe": timeframe.value},
        )

    limit = max_history(timeframe)
    if limit is None:
        return

    requested_span = end - start
    if requested_span > limit:
        raise PlanRestrictionError(
            f"The {PLAN_NAME} plan only grants {limit.days} days of history at "
            f"{timeframe.value}, but {requested_span.days} days were requested",
            plan=PLAN_NAME,
            context={
                "timeframe": timeframe.value,
                "requested_days": requested_span.days,
                "max_days": limit.days,
            },
        )
