"""Validates raw funding rate history before it's analyzed.

Checks the things a *data quality* problem, not a strategy rule, could
cause: a missing reading, a malformed timestamp, a duplicated record, an
unexplained gap, or a statistical outlier. Outlier and gap detection are
both opt-in via :class:`~btengine.analysis.funding_rate.config.FundingRateAnalysisConfig`
placeholders — this module never assumes a threshold or an expected
interval on your behalf.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from btengine.analysis.funding_rate.config import FundingRateAnalysisConfig
from btengine.analysis.funding_rate.models import FundingRateObservation

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class FundingDataValidationIssue:
    severity: Severity
    message: str
    timestamp: datetime | None = None


class FundingDataValidator:
    """Runs every check and returns the full list of issues found."""

    def __init__(self, config: FundingRateAnalysisConfig | None = None) -> None:
        self._config = config or FundingRateAnalysisConfig()

    def validate(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        issues: list[FundingDataValidationIssue] = []
        issues += self._check_missing(observations)
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_outliers(observations)
        issues += self._check_gaps(observations)
        return issues

    def _check_missing(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        return [
            FundingDataValidationIssue(
                "WARNING", "missing funding_rate value", observation.timestamp
            )
            for observation in observations
            if observation.funding_rate is None
        ]

    def _check_timestamps(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        return [
            FundingDataValidationIssue(
                "ERROR", "naive (non-timezone-aware) timestamp", observation.timestamp
            )
            for observation in observations
            if observation.timestamp.tzinfo is None
        ]

    def _check_duplicates(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        counts: dict[datetime, int] = {}
        for observation in observations:
            counts[observation.timestamp] = counts.get(observation.timestamp, 0) + 1

        issues: list[FundingDataValidationIssue] = []
        for timestamp, count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    FundingDataValidationIssue(
                        "ERROR", f"duplicate timestamp occurs {count} times", timestamp
                    )
                )
        return issues

    def _check_outliers(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        threshold = self._config.outlier_zscore_threshold
        if threshold is None:
            return []

        values = [o.funding_rate for o in observations if o.funding_rate is not None]
        if len(values) < 2:
            return []

        mean = statistics.mean(values)
        stdev = statistics.pstdev(values)
        if stdev == 0:
            return []

        issues: list[FundingDataValidationIssue] = []
        for observation in observations:
            if observation.funding_rate is None:
                continue
            zscore = (observation.funding_rate - mean) / stdev
            if abs(zscore) > threshold:
                issues.append(
                    FundingDataValidationIssue(
                        "WARNING",
                        f"outlier funding_rate {observation.funding_rate} (|z|={abs(zscore):.2f} "
                        f"> {threshold})",
                        observation.timestamp,
                    )
                )
        return issues

    def _check_gaps(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        expected_interval = self._config.expected_interval
        if expected_interval is None:
            return []

        ordered = sorted(observations, key=lambda o: o.timestamp)
        issues: list[FundingDataValidationIssue] = []
        for previous, current in zip(ordered, ordered[1:]):
            gap = current.timestamp - previous.timestamp
            if gap > expected_interval:
                issues.append(
                    FundingDataValidationIssue(
                        "WARNING",
                        f"gap of {gap} exceeds expected interval of {expected_interval}",
                        current.timestamp,
                    )
                )
        return issues
