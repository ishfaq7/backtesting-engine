"""Validates raw Open Interest history before it's analyzed.

Checks the things a *data quality* problem, not a strategy rule, could
cause: a missing reading, a malformed timestamp, a duplicated record, an
unexplained gap, or a statistical outlier. Outlier and gap detection are
both opt-in via :class:`~btengine.analysis.open_interest.config.OpenInterestAnalysisConfig`
placeholders — this module never assumes a threshold or an expected
interval on your behalf.

This is distinct from the engine's ``is_abnormal_spike`` analysis output:
this validator flags an Open Interest *level* that looks like bad data;
the engine separately (and always, given enough history) measures how
unusual the latest Open Interest *change* was, as a descriptive
statistic rather than a data-quality judgment.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from btengine.analysis.open_interest.config import OpenInterestAnalysisConfig
from btengine.analysis.open_interest.models import OpenInterestObservation

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class OpenInterestDataValidationIssue:
    severity: Severity
    message: str
    timestamp: datetime | None = None


class OpenInterestDataValidator:
    """Runs every check and returns the full list of issues found."""

    def __init__(self, config: OpenInterestAnalysisConfig | None = None) -> None:
        self._config = config or OpenInterestAnalysisConfig()

    def validate(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        issues: list[OpenInterestDataValidationIssue] = []
        issues += self._check_missing(observations)
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_outliers(observations)
        issues += self._check_gaps(observations)
        return issues

    def _check_missing(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        return [
            OpenInterestDataValidationIssue(
                "WARNING", "missing open_interest value", observation.timestamp
            )
            for observation in observations
            if observation.open_interest is None
        ]

    def _check_timestamps(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        return [
            OpenInterestDataValidationIssue(
                "ERROR", "naive (non-timezone-aware) timestamp", observation.timestamp
            )
            for observation in observations
            if observation.timestamp.tzinfo is None
        ]

    def _check_duplicates(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        counts: dict[datetime, int] = {}
        for observation in observations:
            counts[observation.timestamp] = counts.get(observation.timestamp, 0) + 1

        issues: list[OpenInterestDataValidationIssue] = []
        for timestamp, count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    OpenInterestDataValidationIssue(
                        "ERROR", f"duplicate timestamp occurs {count} times", timestamp
                    )
                )
        return issues

    def _check_outliers(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        threshold = self._config.outlier_zscore_threshold
        if threshold is None:
            return []

        values = [o.open_interest for o in observations if o.open_interest is not None]
        if len(values) < 2:
            return []

        mean = statistics.mean(values)
        stdev = statistics.pstdev(values)
        if stdev == 0:
            return []

        issues: list[OpenInterestDataValidationIssue] = []
        for observation in observations:
            if observation.open_interest is None:
                continue
            zscore = (observation.open_interest - mean) / stdev
            if abs(zscore) > threshold:
                issues.append(
                    OpenInterestDataValidationIssue(
                        "WARNING",
                        f"outlier open_interest {observation.open_interest} (|z|={abs(zscore):.2f} "
                        f"> {threshold})",
                        observation.timestamp,
                    )
                )
        return issues

    def _check_gaps(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        expected_interval = self._config.expected_interval
        if expected_interval is None:
            return []

        ordered = sorted(observations, key=lambda o: o.timestamp)
        issues: list[OpenInterestDataValidationIssue] = []
        for previous, current in zip(ordered, ordered[1:]):
            gap = current.timestamp - previous.timestamp
            if gap > expected_interval:
                issues.append(
                    OpenInterestDataValidationIssue(
                        "WARNING",
                        f"gap of {gap} exceeds expected interval of {expected_interval}",
                        current.timestamp,
                    )
                )
        return issues
