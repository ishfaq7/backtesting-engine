"""Validates raw OHLC candle history before it's analyzed.

Checks the things a *data quality* problem, not a strategy rule, could
cause: a missing candle, an internally invalid candle (``high < low``,
which would corrupt swing detection), a malformed timestamp, a
duplicated record, an unexplained gap, or a statistical outlier close
price. Outlier and gap detection are both opt-in via
:class:`~btengine.analysis.premium_discount.config.PremiumDiscountAnalysisConfig`
placeholders — this module never assumes a threshold or an expected
interval on your behalf.

This is distinct from the engine's own "invalid range" check (raised in
``analyze()`` when the *computed* active high/low don't form a usable
range) — this validator only inspects the raw, per-candle input.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from btengine.analysis.premium_discount.config import PremiumDiscountAnalysisConfig
from btengine.analysis.premium_discount.models import CandleObservation

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class PremiumDiscountValidationIssue:
    severity: Severity
    message: str
    timestamp: datetime | None = None


class PremiumDiscountValidator:
    """Runs every check and returns the full list of issues found."""

    def __init__(self, config: PremiumDiscountAnalysisConfig | None = None) -> None:
        self._config = config or PremiumDiscountAnalysisConfig()

    def validate(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        issues: list[PremiumDiscountValidationIssue] = []
        issues += self._check_missing(candles)
        issues += self._check_invalid_candles(candles)
        issues += self._check_timestamps(candles)
        issues += self._check_duplicates(candles)
        issues += self._check_outliers(candles)
        issues += self._check_gaps(candles)
        return issues

    def _check_missing(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        return [
            PremiumDiscountValidationIssue(
                "WARNING", "missing candle data (high/low/close)", candle.timestamp
            )
            for candle in candles
            if candle.high is None or candle.low is None or candle.close is None
        ]

    def _check_invalid_candles(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        return [
            PremiumDiscountValidationIssue(
                "ERROR", f"invalid candle: high ({candle.high}) < low ({candle.low})", candle.timestamp
            )
            for candle in candles
            if candle.high is not None and candle.low is not None and candle.high < candle.low
        ]

    def _check_timestamps(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        return [
            PremiumDiscountValidationIssue(
                "ERROR", "naive (non-timezone-aware) timestamp", candle.timestamp
            )
            for candle in candles
            if candle.timestamp.tzinfo is None
        ]

    def _check_duplicates(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        counts: dict[datetime, int] = {}
        for candle in candles:
            counts[candle.timestamp] = counts.get(candle.timestamp, 0) + 1

        issues: list[PremiumDiscountValidationIssue] = []
        for timestamp, count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    PremiumDiscountValidationIssue(
                        "ERROR", f"duplicate timestamp occurs {count} times", timestamp
                    )
                )
        return issues

    def _check_outliers(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        threshold = self._config.outlier_zscore_threshold
        if threshold is None:
            return []

        closes = [candle.close for candle in candles if candle.close is not None]
        if len(closes) < 2:
            return []

        mean = statistics.mean(closes)
        stdev = statistics.pstdev(closes)
        if stdev == 0:
            return []

        issues: list[PremiumDiscountValidationIssue] = []
        for candle in candles:
            if candle.close is None:
                continue
            zscore = (candle.close - mean) / stdev
            if abs(zscore) > threshold:
                issues.append(
                    PremiumDiscountValidationIssue(
                        "WARNING",
                        f"outlier close {candle.close} (|z|={abs(zscore):.2f} > {threshold})",
                        candle.timestamp,
                    )
                )
        return issues

    def _check_gaps(
        self, candles: Sequence[CandleObservation]
    ) -> list[PremiumDiscountValidationIssue]:
        expected_interval = self._config.expected_interval
        if expected_interval is None:
            return []

        ordered = sorted(candles, key=lambda candle: candle.timestamp)
        issues: list[PremiumDiscountValidationIssue] = []
        for previous, current in zip(ordered, ordered[1:]):
            gap = current.timestamp - previous.timestamp
            if gap > expected_interval:
                issues.append(
                    PremiumDiscountValidationIssue(
                        "WARNING",
                        f"gap of {gap} exceeds expected interval of {expected_interval}",
                        current.timestamp,
                    )
                )
        return issues
