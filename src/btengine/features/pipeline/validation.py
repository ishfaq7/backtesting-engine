"""Validates Feature Engineering Pipeline output for data-quality problems
this layer itself could introduce.

Input records (``Candle``, ``FundingRate``, ...) are already validated by
their own canonical schema (:mod:`btengine.data.schema`) before they ever
reach this pipeline — a naive timestamp, a missing field, or a malformed
value is already impossible to construct one of those models with. This
validator therefore focuses on what's genuinely new here: bugs a feature
*computation* could introduce (a division producing NaN/Inf that slipped
past :func:`~btengine.features.pipeline.base.frame_to_feature_values`'s
filtering, a windowing bug producing duplicate or out-of-order
timestamps) — never a judgment about whether a computed value is
"reasonable."
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from btengine.features.base import FeatureValue

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class FeatureValidationIssue:
    severity: Severity
    feature_name: str
    message: str


class FeaturePipelineValidator:
    """Runs every check and returns the full list of issues found (empty
    if every feature value is well-formed and internally consistent).
    """

    def validate(self, features: list[FeatureValue]) -> list[FeatureValidationIssue]:
        issues: list[FeatureValidationIssue] = []
        issues += self._check_nan_and_inf(features)
        issues += self._check_timestamps(features)
        issues += self._check_duplicates(features)
        issues += self._check_monotonic_series(features)
        return issues

    def _check_nan_and_inf(self, features: list[FeatureValue]) -> list[FeatureValidationIssue]:
        issues: list[FeatureValidationIssue] = []
        for feature in features:
            if math.isnan(feature.value):
                issues.append(
                    FeatureValidationIssue(
                        "ERROR", feature.feature_name,
                        f"NaN value for {feature.symbol} at {feature.timestamp.isoformat()}",
                    )
                )
            elif math.isinf(feature.value):
                issues.append(
                    FeatureValidationIssue(
                        "ERROR", feature.feature_name,
                        f"infinite value for {feature.symbol} at {feature.timestamp.isoformat()}",
                    )
                )
        return issues

    def _check_timestamps(self, features: list[FeatureValue]) -> list[FeatureValidationIssue]:
        issues: list[FeatureValidationIssue] = []
        for feature in features:
            if feature.timestamp.tzinfo is None:
                issues.append(
                    FeatureValidationIssue(
                        "ERROR", feature.feature_name,
                        f"naive (non-timezone-aware) timestamp for {feature.symbol}",
                    )
                )
        return issues

    def _check_duplicates(self, features: list[FeatureValue]) -> list[FeatureValidationIssue]:
        counts: dict[tuple[str, str, object, str], int] = {}
        for feature in features:
            key = (feature.symbol, feature.feature_name, feature.timestamp, feature.version)
            counts[key] = counts.get(key, 0) + 1

        issues: list[FeatureValidationIssue] = []
        for (symbol, feature_name, timestamp, version), count in sorted(
            counts.items(), key=lambda item: (item[0][1], item[0][0])
        ):
            if count > 1:
                issues.append(
                    FeatureValidationIssue(
                        "ERROR", feature_name,
                        f"duplicate ({symbol}, {timestamp}, version={version}) occurs {count} times",
                    )
                )
        return issues

    def _check_monotonic_series(self, features: list[FeatureValue]) -> list[FeatureValidationIssue]:
        by_series: dict[tuple[str, str, str], list] = {}
        for feature in sorted(features, key=lambda f: f.timestamp):
            key = (feature.symbol, feature.feature_name, feature.version)
            by_series.setdefault(key, []).append(feature.timestamp)

        issues: list[FeatureValidationIssue] = []
        for (symbol, feature_name, _version), timestamps in sorted(by_series.items(), key=lambda kv: kv[0][1]):
            for previous, current in zip(timestamps, timestamps[1:]):
                if current <= previous:
                    issues.append(
                        FeatureValidationIssue(
                            "ERROR", feature_name,
                            f"timestamps not strictly increasing for {symbol}: "
                            f"{previous.isoformat()} -> {current.isoformat()}",
                        )
                    )
        return issues
