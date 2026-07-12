"""Validates raw multi-source liquidity data before it's analyzed.

Checks the things a *data quality* problem, not a strategy rule, could
cause: a missing reading, a malformed timestamp, a duplicated
(timestamp, exchange) record, an unexplained gap, a statistical outlier,
or a configured exchange selection that doesn't actually appear in any
of the given data ("exchange inconsistency"). Outlier and gap detection
are both opt-in via
:class:`~btengine.analysis.liquidity.config.LiquidityAnalysisConfig`
placeholders — this module never assumes a threshold or an expected
interval on your behalf.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from btengine.analysis.liquidity.config import LiquidityAnalysisConfig
from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class LiquidityValidationIssue:
    severity: Severity
    message: str
    timestamp: datetime | None = None


class LiquidityDataValidator:
    """Runs every check across every provided source and returns the full issue list."""

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
        issues: list[LiquidityValidationIssue] = []
        issues += self._check_liquidations(liquidations)
        issues += self._check_ratio("global_ratio", global_ratio)
        issues += self._check_ratio("top_trader_account_ratio", top_trader_account_ratio)
        issues += self._check_ratio("top_trader_position_ratio", top_trader_position_ratio)
        issues += self._check_open_interest(open_interest)
        issues += self._check_price(price)
        issues += self._check_exchange_consistency(
            liquidations, global_ratio, top_trader_account_ratio, top_trader_position_ratio,
            open_interest, price,
        )
        return issues

    # --- per-source checks -------------------------------------------------

    def _check_liquidations(
        self, observations: Sequence[LiquidationObservation]
    ) -> list[LiquidityValidationIssue]:
        issues: list[LiquidityValidationIssue] = []
        issues += [
            LiquidityValidationIssue("WARNING", "missing liquidation data", o.timestamp)
            for o in observations
            if o.long_liquidation_usd is None or o.short_liquidation_usd is None
        ]
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_gaps_by_exchange(observations)
        totals = [
            o.long_liquidation_usd + o.short_liquidation_usd
            for o in observations
            if o.long_liquidation_usd is not None and o.short_liquidation_usd is not None
        ]
        timestamps = [
            o.timestamp
            for o in observations
            if o.long_liquidation_usd is not None and o.short_liquidation_usd is not None
        ]
        issues += self._check_outliers(totals, timestamps, "total liquidation volume")
        return issues

    def _check_ratio(
        self, label: str, observations: Sequence[RatioObservation]
    ) -> list[LiquidityValidationIssue]:
        issues: list[LiquidityValidationIssue] = []
        issues += [
            LiquidityValidationIssue("WARNING", f"missing {label} data", o.timestamp)
            for o in observations
            if o.long_account_ratio is None or o.short_account_ratio is None
        ]
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_gaps_by_exchange(observations)
        values = [o.long_account_ratio for o in observations if o.long_account_ratio is not None]
        timestamps = [o.timestamp for o in observations if o.long_account_ratio is not None]
        issues += self._check_outliers(values, timestamps, f"{label} long_account_ratio")
        return issues

    def _check_open_interest(
        self, observations: Sequence[OpenInterestObservation]
    ) -> list[LiquidityValidationIssue]:
        issues: list[LiquidityValidationIssue] = []
        issues += [
            LiquidityValidationIssue("WARNING", "missing open interest data", o.timestamp)
            for o in observations
            if o.open_interest is None
        ]
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_gaps_by_exchange(observations)
        values = [o.open_interest for o in observations if o.open_interest is not None]
        timestamps = [o.timestamp for o in observations if o.open_interest is not None]
        issues += self._check_outliers(values, timestamps, "open interest")
        return issues

    def _check_price(self, observations: Sequence[PriceObservation]) -> list[LiquidityValidationIssue]:
        issues: list[LiquidityValidationIssue] = []
        issues += [
            LiquidityValidationIssue("WARNING", "missing price data", o.timestamp)
            for o in observations
            if o.close is None
        ]
        issues += self._check_timestamps(observations)
        issues += self._check_duplicates(observations)
        issues += self._check_gaps_by_exchange(observations)
        values = [o.close for o in observations if o.close is not None]
        timestamps = [o.timestamp for o in observations if o.close is not None]
        issues += self._check_outliers(values, timestamps, "price")
        return issues

    # --- generic, source-agnostic checks ------------------------------------

    def _check_timestamps(self, observations: Sequence[object]) -> list[LiquidityValidationIssue]:
        return [
            LiquidityValidationIssue(
                "ERROR", "naive (non-timezone-aware) timestamp", observation.timestamp  # type: ignore[attr-defined]
            )
            for observation in observations
            if observation.timestamp.tzinfo is None  # type: ignore[attr-defined]
        ]

    def _check_duplicates(self, observations: Sequence[object]) -> list[LiquidityValidationIssue]:
        counts: dict[tuple[datetime, str], int] = {}
        for observation in observations:
            key = (observation.timestamp, observation.exchange)  # type: ignore[attr-defined]
            counts[key] = counts.get(key, 0) + 1

        issues: list[LiquidityValidationIssue] = []
        for (timestamp, exchange), count in sorted(counts.items()):
            if count > 1:
                issues.append(
                    LiquidityValidationIssue(
                        "ERROR",
                        f"duplicate (timestamp, exchange) = ({timestamp}, {exchange}) occurs {count} times",
                        timestamp,
                    )
                )
        return issues

    def _check_gaps_by_exchange(self, observations: Sequence[object]) -> list[LiquidityValidationIssue]:
        expected_interval = self._config.expected_interval
        if expected_interval is None:
            return []

        by_exchange: dict[str, list[datetime]] = {}
        for observation in observations:
            by_exchange.setdefault(observation.exchange, []).append(observation.timestamp)  # type: ignore[attr-defined]

        issues: list[LiquidityValidationIssue] = []
        for exchange, timestamps in sorted(by_exchange.items()):
            ordered = sorted(timestamps)
            for previous, current in zip(ordered, ordered[1:]):
                gap = current - previous
                if gap > expected_interval:
                    issues.append(
                        LiquidityValidationIssue(
                            "WARNING",
                            f"gap of {gap} on exchange {exchange!r} exceeds expected interval "
                            f"of {expected_interval}",
                            current,
                        )
                    )
        return issues

    def _check_outliers(
        self, values: Sequence[float], timestamps: Sequence[datetime], label: str
    ) -> list[LiquidityValidationIssue]:
        threshold = self._config.outlier_zscore_threshold
        if threshold is None or len(values) < 2:
            return []

        mean = statistics.mean(values)
        stdev = statistics.pstdev(values)
        if stdev == 0:
            return []

        issues: list[LiquidityValidationIssue] = []
        for value, timestamp in zip(values, timestamps):
            zscore = (value - mean) / stdev
            if abs(zscore) > threshold:
                issues.append(
                    LiquidityValidationIssue(
                        "WARNING",
                        f"outlier {label} {value} (|z|={abs(zscore):.2f} > {threshold})",
                        timestamp,
                    )
                )
        return issues

    def _check_exchange_consistency(self, *series: Sequence[object]) -> list[LiquidityValidationIssue]:
        if self._config.exchange_selection is None:
            return []

        observed_exchanges = {
            observation.exchange for observations in series for observation in observations  # type: ignore[attr-defined]
        }
        return [
            LiquidityValidationIssue(
                "WARNING", f"selected exchange {exchange!r} not found in any provided data"
            )
            for exchange in self._config.exchange_selection
            if exchange not in observed_exchanges
        ]
