"""The Liquidity Analysis Engine.

Turns liquidation, positioning-ratio, and (read-only) open-interest/price
history into one :class:`~btengine.analysis.liquidity.models.LiquidityAnalysis`
snapshot. Every computation here is a plain descriptive statistic —
volumes, ratios, z-scores, trends of a ratio. Nothing in this module
decides whether current liquidity conditions are a good entry, computes
a composite score, manages risk, or emits a BUY/SELL signal.

Six named inputs (only ``liquidations`` is required; the rest default to
empty and leave their corresponding output fields ``None``) mirror this
task's INPUT section exactly, and match this module's own decoupled
``*Observation`` types so it stays reusable outside any one upstream
schema or provider (see :mod:`~btengine.analysis.liquidity.integration`).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from btengine.analysis.liquidity.config import LiquidityAnalysisConfig
from btengine.analysis.liquidity.errors import LiquidityAnalysisError
from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    LiquidityAnalysis,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)
from btengine.analysis.liquidity.stats import (
    aggregate_by_timestamp,
    align_two_series,
    compute_bias,
    half_split_delta,
    zscore_of_latest,
)
from btengine.analysis.liquidity.validation import LiquidityDataValidator, LiquidityValidationIssue


class LiquidityAnalysisEngine:
    """Reusable, stateless engine that turns multi-source liquidity data into a :class:`LiquidityAnalysis`."""

    def __init__(self, config: LiquidityAnalysisConfig | None = None) -> None:
        self._config = config or LiquidityAnalysisConfig()

    def validate(
        self,
        *,
        liquidations: Sequence[LiquidationObservation] = (),
        global_ratio: Sequence[RatioObservation] = (),
        top_trader_account_ratio: Sequence[RatioObservation] = (),
        top_trader_position_ratio: Sequence[RatioObservation] = (),
        open_interest: Sequence[OpenInterestObservation] = (),
        price: Sequence[PriceObservation] = (),
    ) -> list[LiquidityValidationIssue]:
        """Run data-quality checks on the raw, as-given multi-source data."""
        return LiquidityDataValidator(self._config).validate(
            liquidations=liquidations,
            global_ratio=global_ratio,
            top_trader_account_ratio=top_trader_account_ratio,
            top_trader_position_ratio=top_trader_position_ratio,
            open_interest=open_interest,
            price=price,
        )

    def analyze(
        self,
        symbol: str,
        *,
        liquidations: Sequence[LiquidationObservation],
        global_ratio: Sequence[RatioObservation] = (),
        top_trader_account_ratio: Sequence[RatioObservation] = (),
        top_trader_position_ratio: Sequence[RatioObservation] = (),
        open_interest: Sequence[OpenInterestObservation] = (),
        price: Sequence[PriceObservation] = (),
    ) -> LiquidityAnalysis:
        """Compute a :class:`LiquidityAnalysis` snapshot as of the latest liquidation reading.

        ``liquidations`` is the only required input; every other source
        is optional and its dependent output fields stay ``None`` when
        omitted. Missing/invalid readings are excluded; duplicate
        (timestamp, exchange) pairs keep the last-given reading; every
        series is sorted chronologically regardless of input order.
        Raises :class:`~btengine.analysis.liquidity.errors.LiquidityAnalysisError`
        if no usable liquidation reading remains after cleaning.
        """
        cleaned_liquidations = self._clean(liquidations, self._has_liquidation_value)
        if not cleaned_liquidations:
            raise LiquidityAnalysisError(f"no usable liquidation observations for {symbol!r}")

        cleaned_global = self._clean(global_ratio, self._has_ratio_value)
        cleaned_account = self._clean(top_trader_account_ratio, self._has_ratio_value)
        cleaned_position = self._clean(top_trader_position_ratio, self._has_ratio_value)
        cleaned_oi = self._clean(open_interest, lambda o: o.open_interest is not None)
        cleaned_price = self._clean(price, lambda o: o.close is not None)

        method = self._config.aggregation_method
        window = self._config.analysis_window

        long_agg = aggregate_by_timestamp(
            [(o.timestamp, o.long_liquidation_usd) for o in cleaned_liquidations], method
        )
        short_agg = aggregate_by_timestamp(
            [(o.timestamp, o.short_liquidation_usd) for o in cleaned_liquidations], method
        )
        total_agg = aggregate_by_timestamp(
            [(o.timestamp, o.long_liquidation_usd + o.short_liquidation_usd) for o in cleaned_liquidations],
            method,
        )

        windowed_long = long_agg[-window:]
        windowed_short = short_agg[-window:]
        windowed_total = total_agg[-window:]

        long_liquidation_volume = sum(value for _, value in windowed_long)
        short_liquidation_volume = sum(value for _, value in windowed_short)
        total_liquidation_volume = long_liquidation_volume + short_liquidation_volume
        liquidation_event_count = len(windowed_total)
        liquidation_bias = compute_bias(long_liquidation_volume, short_liquidation_volume)

        spike_values = [value for _, value in total_agg[-self._config.spike_window :]]
        liquidation_intensity = zscore_of_latest(spike_values)
        is_abnormal_liquidation = self._classify_spike(liquidation_intensity)

        long_short_ratio = self._latest_ratio(cleaned_global, method)
        top_trader_account_bias = self._latest_bias(cleaned_account, method)
        top_trader_position_bias = self._latest_bias(cleaned_position, method)
        top_trader_bias = (
            top_trader_position_bias if cleaned_position else top_trader_account_bias
        )

        market_crowdedness = self._market_crowdedness(cleaned_global, method, window)

        oi_agg = aggregate_by_timestamp(
            [(o.timestamp, o.open_interest) for o in cleaned_oi], method
        )
        market_participation = self._market_participation(oi_agg, window)
        current_open_interest = oi_agg[-1][1] if oi_agg else None

        price_agg = aggregate_by_timestamp([(o.timestamp, o.close) for o in cleaned_price], method)
        current_price = price_agg[-1][1] if price_agg else None

        liquidity_pressure, liquidity_shift = self._liquidity_pressure_and_shift(
            total_agg, oi_agg, window
        )

        exchange_liquidation_totals = self._exchange_liquidation_totals(
            cleaned_liquidations, {timestamp for timestamp, _ in windowed_total}
        )

        return LiquidityAnalysis(
            symbol=symbol.upper(),
            as_of=cleaned_liquidations[-1].timestamp,
            sample_size=liquidation_event_count,
            confidence_level=self._confidence(liquidation_event_count),
            long_liquidation_volume=long_liquidation_volume,
            short_liquidation_volume=short_liquidation_volume,
            total_liquidation_volume=total_liquidation_volume,
            liquidation_event_count=liquidation_event_count,
            liquidation_bias=liquidation_bias,
            liquidation_intensity=liquidation_intensity,
            is_abnormal_liquidation=is_abnormal_liquidation,
            long_short_ratio=long_short_ratio,
            top_trader_account_bias=top_trader_account_bias,
            top_trader_position_bias=top_trader_position_bias,
            top_trader_bias=top_trader_bias,
            market_crowdedness=market_crowdedness,
            market_participation=market_participation,
            current_open_interest=current_open_interest,
            current_price=current_price,
            liquidity_pressure=liquidity_pressure,
            liquidity_shift=liquidity_shift,
            exchange_liquidation_totals=exchange_liquidation_totals,
        )

    # --- cleaning ------------------------------------------------------

    @staticmethod
    def _has_liquidation_value(observation: LiquidationObservation) -> bool:
        return observation.long_liquidation_usd is not None and observation.short_liquidation_usd is not None

    @staticmethod
    def _has_ratio_value(observation: RatioObservation) -> bool:
        return observation.long_account_ratio is not None and observation.short_account_ratio is not None

    def _clean(self, observations, is_usable) -> list:
        selected = self._select_exchanges(observations)
        by_key: dict[tuple[datetime, str], object] = {}
        for observation in selected:
            if not is_usable(observation):
                continue
            by_key[(observation.timestamp, observation.exchange)] = observation  # last-given wins
        return [by_key[key] for key in sorted(by_key)]

    def _select_exchanges(self, observations: Sequence[object]) -> list[object]:
        if self._config.exchange_selection is None:
            return list(observations)
        allowed = set(self._config.exchange_selection)
        return [o for o in observations if o.exchange in allowed]  # type: ignore[attr-defined]

    # --- computations ----------------------------------------------------

    def _classify_spike(self, intensity: float | None) -> bool | None:
        threshold = self._config.spike_zscore_threshold
        if intensity is None or threshold is None:
            return None
        return abs(intensity) > threshold

    def _latest_ratio(self, observations: list[RatioObservation], method) -> float | None:
        if not observations:
            return None
        long_agg = aggregate_by_timestamp([(o.timestamp, o.long_account_ratio) for o in observations], method)
        short_agg = aggregate_by_timestamp(
            [(o.timestamp, o.short_account_ratio) for o in observations], method
        )
        latest_short = short_agg[-1][1]
        if latest_short == 0:
            return None
        return long_agg[-1][1] / latest_short

    def _latest_bias(self, observations: list[RatioObservation], method) -> float | None:
        if not observations:
            return None
        long_agg = aggregate_by_timestamp([(o.timestamp, o.long_account_ratio) for o in observations], method)
        short_agg = aggregate_by_timestamp(
            [(o.timestamp, o.short_account_ratio) for o in observations], method
        )
        return compute_bias(long_agg[-1][1], short_agg[-1][1])

    def _market_crowdedness(
        self, observations: list[RatioObservation], method, window: int
    ) -> float | None:
        if not observations:
            return None
        long_agg = aggregate_by_timestamp([(o.timestamp, o.long_account_ratio) for o in observations], method)
        short_agg = aggregate_by_timestamp(
            [(o.timestamp, o.short_account_ratio) for o in observations], method
        )
        biases = [
            bias
            for (_, long_value), (_, short_value) in zip(long_agg, short_agg)
            if (bias := compute_bias(long_value, short_value)) is not None
        ]
        return zscore_of_latest(biases[-window:])

    def _market_participation(self, oi_agg: list[tuple[datetime, float]], window: int) -> float | None:
        windowed = oi_agg[-window:]
        if len(windowed) < 2:
            return None
        earliest = windowed[0][1]
        latest = windowed[-1][1]
        if earliest == 0:
            return None
        return (latest - earliest) / earliest * 100

    def _liquidity_pressure_and_shift(
        self,
        total_agg: list[tuple[datetime, float]],
        oi_agg: list[tuple[datetime, float]],
        window: int,
    ) -> tuple[float | None, float | None]:
        joined = align_two_series(total_agg, oi_agg)
        windowed_joined = joined[-window:]
        if not windowed_joined:
            return None, None

        total_liquidation = sum(liquidation for _, liquidation, _ in windowed_joined)
        average_oi = sum(oi for _, _, oi in windowed_joined) / len(windowed_joined)
        liquidity_pressure = total_liquidation / average_oi if average_oi > 0 else None

        pressures = [liquidation / oi for _, liquidation, oi in windowed_joined if oi > 0]
        liquidity_shift = half_split_delta(pressures)
        return liquidity_pressure, liquidity_shift

    def _exchange_liquidation_totals(
        self, cleaned_liquidations: list[LiquidationObservation], windowed_timestamps: set[datetime]
    ) -> dict[str, float]:
        totals: dict[str, float] = {}
        for observation in cleaned_liquidations:
            if observation.timestamp not in windowed_timestamps:
                continue
            volume = observation.long_liquidation_usd + observation.short_liquidation_usd
            totals[observation.exchange] = totals.get(observation.exchange, 0.0) + volume
        return totals

    def _confidence(self, sample_size: int) -> float:
        required = max(self._config.analysis_window, self._config.spike_window, 1)
        return min(sample_size / required, 1.0)
