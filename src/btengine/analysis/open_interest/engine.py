"""The Open Interest Analysis Engine.

Turns a chronological Open Interest history into one
:class:`~btengine.analysis.open_interest.models.OpenInterestAnalysis`
snapshot. Every computation here is a plain descriptive statistic —
direction of a number, dispersion of a number, min/max/mean of a number,
how many standard deviations the latest change sits from its own recent
history. Nothing in this module decides whether an Open Interest reading
is "good," "bad," bullish, or bearish, and nothing here emits a BUY/SELL
signal or a score.

One engine instance is scoped to one Open Interest *source* — pass
``source_label="aggregated"`` (the default) for a cross-exchange total,
or an exchange name (e.g. ``"binance"``) for an exchange-specific
series. The computations are identical either way; only the label
attached to the output and used to namespace :meth:`OpenInterestAnalysis.to_feature_map`
differs, mirroring how the Feature Engineering Layer's ``FundingFeatures``
and ``LongShortRatioFeatures`` serve multiple CoinGlass sources from one
class via a ``source_label``.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from datetime import datetime

import numpy as np

from btengine.analysis.open_interest.config import OpenInterestAnalysisConfig
from btengine.analysis.open_interest.errors import OpenInterestAnalysisError
from btengine.analysis.open_interest.models import OiDirection, OpenInterestAnalysis, OpenInterestObservation
from btengine.analysis.open_interest.validation import (
    OpenInterestDataValidationIssue,
    OpenInterestDataValidator,
)

# Relative (not absolute) floating-point noise tolerance — see
# _direction_from_value for why this needs to scale with the data.
_FLOAT_NOISE_EPSILON = 1e-15


class OpenInterestAnalysisEngine:
    """Reusable, stateless engine that turns Open Interest history into an :class:`OpenInterestAnalysis`."""

    def __init__(
        self,
        config: OpenInterestAnalysisConfig | None = None,
        *,
        source_label: str = "aggregated",
    ) -> None:
        self._config = config or OpenInterestAnalysisConfig()
        self._source_label = source_label

    @property
    def source_label(self) -> str:
        return self._source_label

    def validate(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestDataValidationIssue]:
        """Run data-quality checks on the raw, as-given observations."""
        return OpenInterestDataValidator(self._config).validate(observations)

    def analyze(self, symbol: str, observations: Sequence[OpenInterestObservation]) -> OpenInterestAnalysis:
        """Compute an :class:`OpenInterestAnalysis` snapshot as of the latest observation.

        Missing (``None``) readings are excluded from every computation;
        duplicate timestamps keep the last-given reading; the series is
        sorted chronologically regardless of input order. Raises
        :class:`~btengine.analysis.open_interest.errors.OpenInterestAnalysisError`
        if no usable reading remains after cleaning.
        """
        cleaned = self._clean(observations)
        if not cleaned:
            raise OpenInterestAnalysisError(
                f"no usable open interest observations to analyze for {symbol!r}"
            )

        values = [observation.open_interest for observation in cleaned]
        assert all(value is not None for value in values)  # narrowed by _clean

        current_oi = values[-1]
        previous_oi = values[-2] if len(values) >= 2 else None
        oi_change = current_oi - previous_oi if previous_oi is not None else None
        oi_change_pct = (
            oi_change / previous_oi if oi_change is not None and previous_oi != 0 else None
        )

        trend_direction, trend_value = self._detect_trend(values)
        momentum_direction, momentum_value = self._detect_momentum(values)
        volatility = self._detect_volatility(values)
        is_abnormal_spike, spike_magnitude = self._detect_spike(values)

        history = (
            values[-self._config.historical_window :]
            if self._config.historical_window is not None
            else values
        )
        historical_average = statistics.mean(history) if history else None
        historical_maximum = max(history) if history else None
        historical_minimum = min(history) if history else None

        return OpenInterestAnalysis(
            symbol=symbol.upper(),
            source=self._source_label,
            as_of=cleaned[-1].timestamp,
            current_oi=current_oi,
            previous_oi=previous_oi,
            oi_change=oi_change,
            oi_change_pct=oi_change_pct,
            oi_trend=trend_direction,
            oi_trend_value=trend_value,
            oi_momentum=momentum_direction,
            oi_momentum_value=momentum_value,
            oi_volatility=volatility,
            is_abnormal_spike=is_abnormal_spike,
            spike_magnitude=spike_magnitude,
            historical_average=historical_average,
            historical_maximum=historical_maximum,
            historical_minimum=historical_minimum,
            sample_size=len(values),
            confidence_level=self._confidence(len(values)),
        )

    def _clean(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[OpenInterestObservation]:
        by_timestamp: dict[datetime, OpenInterestObservation] = {}
        for observation in observations:
            if observation.open_interest is None:
                continue
            by_timestamp[observation.timestamp] = observation  # last-given wins
        return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]

    def _detect_trend(self, values: list[float]) -> tuple[OiDirection, float | None]:
        window = values[-self._config.trend_window :]
        if len(window) < 2:
            return OiDirection.UNKNOWN, None

        x = np.arange(len(window), dtype=float)
        slope = float(np.polyfit(x, np.asarray(window, dtype=float), 1)[0])
        return self._direction_from_value(slope, window), slope

    def _detect_momentum(self, values: list[float]) -> tuple[OiDirection, float | None]:
        window = values[-self._config.momentum_window :]
        if len(window) < 2:
            return OiDirection.UNKNOWN, None

        # window has >= 2 elements here, so a midpoint split always yields two
        # non-empty halves.
        midpoint = len(window) // 2
        first_half, second_half = window[:midpoint], window[midpoint:]
        momentum = statistics.mean(second_half) - statistics.mean(first_half)
        return self._direction_from_value(momentum, window), momentum

    def _detect_volatility(self, values: list[float]) -> float | None:
        window = values[-self._config.volatility_window :]
        if len(window) < 2:
            return None
        return statistics.stdev(window)

    def _detect_spike(self, values: list[float]) -> tuple[bool | None, float | None]:
        """Measure how unusual the latest change is against its own recent history.

        ``spike_magnitude`` (a z-score) is computed whenever enough
        history exists, independent of configuration.
        ``is_abnormal_spike`` only becomes a boolean once
        ``spike_zscore_threshold`` is configured — until then it stays
        ``None`` rather than being classified against an invented cutoff.
        """
        window = values[-self._config.spike_window :]
        changes = [current - previous for previous, current in zip(window, window[1:])]
        if len(changes) < 2:
            return None, None

        baseline, latest_change = changes[:-1], changes[-1]
        if len(baseline) < 2:
            return None, None

        baseline_stdev = statistics.stdev(baseline)
        if baseline_stdev == 0:
            return None, None

        zscore = (latest_change - statistics.mean(baseline)) / baseline_stdev
        threshold = self._config.spike_zscore_threshold
        is_abnormal_spike = None if threshold is None else abs(zscore) > threshold
        return is_abnormal_spike, zscore

    def _confidence(self, sample_size: int) -> float:
        required = max(
            self._config.trend_window,
            self._config.momentum_window,
            self._config.volatility_window,
            self._config.spike_window,
            self._config.historical_window or 0,
            1,
        )
        return min(sample_size / required, 1.0)

    @staticmethod
    def _direction_from_value(value: float, window: list[float]) -> OiDirection:
        # A tolerance around zero, not a trading threshold: it only absorbs
        # floating-point noise (e.g. linear regression on an exactly constant
        # series can yield a slope like -1.2e-10 instead of exactly 0.0).
        # Open Interest values span a wide range of magnitudes (single-digit
        # funding-rate-like ratios up to billions of dollars of notional),
        # so the noise floor is scaled to the data's own magnitude rather
        # than a fixed absolute number.
        scale = max((abs(v) for v in window), default=0.0) or 1.0
        if math.isclose(value, 0.0, abs_tol=scale * _FLOAT_NOISE_EPSILON):
            return OiDirection.FLAT
        return OiDirection.RISING if value > 0 else OiDirection.FALLING
