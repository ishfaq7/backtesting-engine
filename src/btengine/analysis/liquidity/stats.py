"""Pure statistical helpers shared across the Liquidity Analysis Engine's
computations.

Isolated from :mod:`~btengine.analysis.liquidity.engine` so each is
independently, thoroughly testable — every named analysis responsibility
(imbalance, intensity, crowdedness, shift) reduces to one of these four
generic functions applied to a different input series, rather than a
bespoke formula per responsibility.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import datetime

from btengine.analysis.liquidity.config import AggregationMethod


def compute_bias(long_value: float, short_value: float) -> float | None:
    """``(long - short) / (long + short)``, in ``[-1, 1]``.

    Positive means the "long" side is currently larger, negative means
    the "short" side is — a fact about the two numbers given, never a
    trading interpretation of them. Returns ``None`` when both are zero
    (the ratio is undefined, not "balanced").
    """
    total = long_value + short_value
    if total == 0:
        return None
    return (long_value - short_value) / total


def aggregate_by_timestamp(
    readings: Sequence[tuple[datetime, float]], method: AggregationMethod
) -> list[tuple[datetime, float]]:
    """Combine same-timestamp readings (e.g. from multiple exchanges) into one series.

    Returns one ``(timestamp, value)`` pair per distinct timestamp,
    sorted chronologically.
    """
    grouped: dict[datetime, list[float]] = {}
    for timestamp, value in readings:
        grouped.setdefault(timestamp, []).append(value)

    if method == AggregationMethod.SUM:
        combine = sum
    elif method == AggregationMethod.MEAN:
        combine = statistics.mean
    else:
        raise NotImplementedError(f"aggregation method {method!r} is not implemented")

    return [(timestamp, combine(values)) for timestamp, values in sorted(grouped.items())]


def zscore_of_latest(values: Sequence[float]) -> float | None:
    """How many standard deviations the last value sits from the mean of the rest.

    ``None`` if there are fewer than 2 baseline values (everything but
    the last) or the baseline has zero spread.
    """
    if len(values) < 2:
        return None
    baseline, latest = values[:-1], values[-1]
    if len(baseline) < 2:
        return None
    stdev = statistics.stdev(baseline)
    if stdev == 0:
        return None
    return (latest - statistics.mean(baseline)) / stdev


def half_split_delta(values: Sequence[float]) -> float | None:
    """``mean(second half) - mean(first half)`` of ``values``.

    A generic "is this series trending up or down over its own recent
    span" statistic. ``None`` if fewer than 2 values are given.
    """
    if len(values) < 2:
        return None
    midpoint = len(values) // 2
    first_half, second_half = values[:midpoint], values[midpoint:]
    return statistics.mean(second_half) - statistics.mean(first_half)


def align_two_series(
    primary: Sequence[tuple[datetime, float]], secondary: Sequence[tuple[datetime, float]]
) -> list[tuple[datetime, float, float]]:
    """Inner-join two ``(timestamp, value)`` series on shared timestamps.

    Returns ``(timestamp, primary_value, secondary_value)`` triples,
    sorted chronologically, for every timestamp present in both inputs.
    """
    secondary_by_timestamp = dict(secondary)
    return sorted(
        (timestamp, value, secondary_by_timestamp[timestamp])
        for timestamp, value in primary
        if timestamp in secondary_by_timestamp
    )
