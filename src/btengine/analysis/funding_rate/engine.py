"""The Funding Rate Analysis Engine.

Turns a chronological funding rate history into one
:class:`~btengine.analysis.funding_rate.models.FundingAnalysis` snapshot.
Every computation here is a plain descriptive statistic — direction of a
number, dispersion of a number, min/max/mean of a number. Nothing in this
module decides whether a funding rate is "good," "bad," bullish, or
bearish, and nothing here emits a BUY/SELL signal or a score.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from datetime import datetime

import numpy as np

from btengine.analysis.funding_rate.config import FundingRateAnalysisConfig
from btengine.analysis.funding_rate.errors import FundingRateAnalysisError
from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection, FundingRateObservation
from btengine.analysis.funding_rate.validation import FundingDataValidationIssue, FundingDataValidator

_FLOAT_NOISE_EPSILON = 1e-15


class FundingRateAnalysisEngine:
    """Reusable, stateless engine that turns funding history into a :class:`FundingAnalysis`."""

    def __init__(self, config: FundingRateAnalysisConfig | None = None) -> None:
        self._config = config or FundingRateAnalysisConfig()

    def validate(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingDataValidationIssue]:
        """Run data-quality checks on the raw, as-given observations."""
        return FundingDataValidator(self._config).validate(observations)

    def analyze(self, symbol: str, observations: Sequence[FundingRateObservation]) -> FundingAnalysis:
        """Compute a :class:`FundingAnalysis` snapshot as of the latest observation.

        Missing (``None``) readings are excluded from every computation;
        duplicate timestamps keep the last-given reading; the series is
        sorted chronologically regardless of input order. Raises
        :class:`~btengine.analysis.funding_rate.errors.FundingRateAnalysisError`
        if no usable reading remains after cleaning.
        """
        cleaned = self._clean(observations)
        if not cleaned:
            raise FundingRateAnalysisError(
                f"no usable funding rate observations to analyze for {symbol!r}"
            )

        values = [observation.funding_rate for observation in cleaned]
        assert all(value is not None for value in values)  # narrowed by _clean

        current_funding = values[-1]
        previous_funding = values[-2] if len(values) >= 2 else None
        funding_change = (
            current_funding - previous_funding if previous_funding is not None else None
        )
        funding_change_pct = (
            funding_change / previous_funding
            if funding_change is not None and previous_funding != 0
            else None
        )

        trend_direction, trend_value = self._detect_trend(values)
        momentum_direction, momentum_value = self._detect_momentum(values)
        volatility = self._detect_volatility(values)

        history = (
            values[-self._config.historical_window :]
            if self._config.historical_window is not None
            else values
        )
        historical_average = statistics.mean(history) if history else None
        historical_maximum = max(history) if history else None
        historical_minimum = min(history) if history else None

        return FundingAnalysis(
            symbol=symbol.upper(),
            as_of=cleaned[-1].timestamp,
            current_funding=current_funding,
            previous_funding=previous_funding,
            funding_change=funding_change,
            funding_change_pct=funding_change_pct,
            funding_trend=trend_direction,
            funding_trend_value=trend_value,
            funding_momentum=momentum_direction,
            funding_momentum_value=momentum_value,
            funding_volatility=volatility,
            historical_average=historical_average,
            historical_maximum=historical_maximum,
            historical_minimum=historical_minimum,
            sample_size=len(values),
            confidence_level=self._confidence(len(values)),
        )

    def _clean(
        self, observations: Sequence[FundingRateObservation]
    ) -> list[FundingRateObservation]:
        by_timestamp: dict[datetime, FundingRateObservation] = {}
        for observation in observations:
            if observation.funding_rate is None:
                continue
            by_timestamp[observation.timestamp] = observation  # last-given wins
        return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]

    def _detect_trend(self, values: list[float]) -> tuple[FundingDirection, float | None]:
        window = values[-self._config.trend_window :]
        if len(window) < 2:
            return FundingDirection.UNKNOWN, None

        x = np.arange(len(window), dtype=float)
        slope = float(np.polyfit(x, np.asarray(window, dtype=float), 1)[0])
        return self._direction_from_value(slope), slope

    def _detect_momentum(self, values: list[float]) -> tuple[FundingDirection, float | None]:
        window = values[-self._config.momentum_window :]
        if len(window) < 2:
            return FundingDirection.UNKNOWN, None

        # window has >= 2 elements here, so a midpoint split always yields two
        # non-empty halves.
        midpoint = len(window) // 2
        first_half, second_half = window[:midpoint], window[midpoint:]
        momentum = statistics.mean(second_half) - statistics.mean(first_half)
        return self._direction_from_value(momentum), momentum

    def _detect_volatility(self, values: list[float]) -> float | None:
        window = values[-self._config.volatility_window :]
        if len(window) < 2:
            return None
        return statistics.stdev(window)

    def _confidence(self, sample_size: int) -> float:
        required = max(
            self._config.trend_window,
            self._config.momentum_window,
            self._config.volatility_window,
            self._config.historical_window or 0,
            1,
        )
        return min(sample_size / required, 1.0)

    @staticmethod
    def _direction_from_value(value: float) -> FundingDirection:
        # A tolerance around zero, not a trading threshold: it only absorbs
        # floating-point noise (e.g. linear regression on an exactly constant
        # series can yield a slope like 1e-21 instead of exactly 0.0).
        if math.isclose(value, 0.0, abs_tol=_FLOAT_NOISE_EPSILON):
            return FundingDirection.FLAT
        return FundingDirection.RISING if value > 0 else FundingDirection.FALLING
