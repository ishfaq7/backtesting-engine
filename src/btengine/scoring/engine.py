"""The Scoring Engine: composes independent Score Providers, a pluggable
Score Aggregator, and a validator into one orchestrator.

Every collaborator is supplied via the constructor (dependency
injection) — this class looks nothing up globally, so a caller can
substitute a different provider, a different aggregator (e.g. a future
AI/ML aggregator — see ``docs/SCORING_ENGINE_FRAMEWORK.md`` §Future
Extension Points), or a different config without editing this file
("Clean Architecture" / SOLID's Dependency Inversion).

This engine never calls CoinGlass, the Feature Store, or any other data
source directly — it only accepts already-computed analysis objects from
the four analyzers. That boundary is deliberate: scoring is a pure
function of already-standardized analytical output, never a second path
back to raw market data.
"""

from __future__ import annotations

import math
from datetime import datetime

from btengine.analysis.funding_rate.models import FundingAnalysis
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis
from btengine.scoring.aggregation import ScoreAggregator, WeightedSumAggregator
from btengine.scoring.config import ConfidenceAggregationMethod, ScoringEngineConfig
from btengine.scoring.models import (
    FeatureStatus,
    ScoreComponent,
    StrategyScore,
    StrategyScoreValidationIssue,
    ValidationStatus,
)
from btengine.scoring.providers.base import ScoreProvider
from btengine.scoring.validation import StrategyScoreValidator


class ScoringEngine:
    """Turns up to four analyzers' outputs into one :class:`StrategyScore`."""

    def __init__(
        self,
        config: ScoringEngineConfig,
        *,
        funding_provider: ScoreProvider[FundingAnalysis] | None = None,
        open_interest_provider: ScoreProvider[OpenInterestAnalysis] | None = None,
        premium_discount_provider: ScoreProvider[PremiumDiscountAnalysis] | None = None,
        liquidity_provider: ScoreProvider[LiquidityAnalysis] | None = None,
        aggregator: ScoreAggregator | None = None,
        validator: StrategyScoreValidator | None = None,
    ) -> None:
        self._config = config
        self._providers: dict[str, ScoreProvider | None] = {
            "funding": funding_provider,
            "open_interest": open_interest_provider,
            "premium_discount": premium_discount_provider,
            "liquidity": liquidity_provider,
        }
        self._aggregator = aggregator or WeightedSumAggregator()
        self._validator = validator or StrategyScoreValidator(config)
        self._seen_calculations: set[tuple[str, datetime, str]] = set()

    def score(
        self,
        symbol: str,
        as_of: datetime,
        *,
        funding: FundingAnalysis | None = None,
        open_interest: OpenInterestAnalysis | None = None,
        premium_discount: PremiumDiscountAnalysis | None = None,
        liquidity: LiquidityAnalysis | None = None,
    ) -> StrategyScore:
        """Compute a :class:`StrategyScore` for ``symbol`` as of ``as_of``.

        Every analysis argument is optional; an omitted one leaves its
        corresponding :class:`~btengine.scoring.models.ScoreComponent`
        ``None`` and its ``feature_status`` entry ``MISSING``. Calling
        this twice with the same ``(symbol, as_of)`` under the same
        ``engine_version`` is flagged as a duplicate calculation
        (``WARNING``), not silently recomputed as if nothing happened.
        """
        analyses: dict[str, object | None] = {
            "funding": funding,
            "open_interest": open_interest,
            "premium_discount": premium_discount,
            "liquidity": liquidity,
        }

        components: dict[str, ScoreComponent | None] = {}
        feature_status: dict[str, FeatureStatus] = {}
        for name, analysis in analyses.items():
            component, status = self._compute_component(name, analysis)
            components[name] = component
            feature_status[name] = status

        issues = list(self._validator.validate(components))
        issues += self._check_duplicate_calculation(symbol, as_of)

        validation_status = self._rollup_validation_status(issues)

        available_components = {
            name: component
            for name, component in components.items()
            if feature_status[name] is FeatureStatus.AVAILABLE
        }
        total_score = (
            self._aggregator.aggregate(available_components, self._config.weights)
            if validation_status is not ValidationStatus.INVALID
            else None
        )

        confidence = self._aggregate_confidence(funding, open_interest, premium_discount, liquidity)

        return StrategyScore(
            symbol=symbol.upper(),
            as_of=as_of,
            score_version=self._config.engine_version,
            funding_score=components["funding"],
            oi_score=components["open_interest"],
            premium_discount_score=components["premium_discount"],
            liquidity_score=components["liquidity"],
            total_score=total_score,
            confidence=confidence,
            feature_status=feature_status,
            validation_status=validation_status,
            validation_issues=tuple(issues),
        )

    def _compute_component(
        self, name: str, analysis: object | None
    ) -> tuple[ScoreComponent | None, FeatureStatus]:
        if analysis is None:
            return None, FeatureStatus.MISSING

        provider = self._providers[name]
        if provider is None:
            return None, FeatureStatus.MISSING

        try:
            component = provider.compute(analysis)
        except NotImplementedError:
            return None, FeatureStatus.NOT_IMPLEMENTED

        if component.value is None:
            return component, FeatureStatus.INVALID
        if math.isnan(component.value) or math.isinf(component.value):
            return component, FeatureStatus.INVALID
        return component, FeatureStatus.AVAILABLE

    def _check_duplicate_calculation(
        self, symbol: str, as_of: datetime
    ) -> list[StrategyScoreValidationIssue]:
        key = (symbol.upper(), as_of, self._config.engine_version)
        if key in self._seen_calculations:
            return [
                StrategyScoreValidationIssue(
                    "WARNING",
                    f"duplicate score calculation for {symbol.upper()} at {as_of} "
                    f"(version {self._config.engine_version})",
                )
            ]
        self._seen_calculations.add(key)
        return []

    def _aggregate_confidence(
        self,
        funding: FundingAnalysis | None,
        open_interest: OpenInterestAnalysis | None,
        premium_discount: PremiumDiscountAnalysis | None,
        liquidity: LiquidityAnalysis | None,
    ) -> float | None:
        values = [
            analysis.confidence_level
            for analysis in (funding, open_interest, premium_discount, liquidity)
            if analysis is not None
        ]
        if not values:
            return None
        if self._config.confidence_aggregation is ConfidenceAggregationMethod.MIN:
            return min(values)
        if self._config.confidence_aggregation is ConfidenceAggregationMethod.MEAN:
            return sum(values) / len(values)
        raise NotImplementedError(
            f"confidence aggregation method {self._config.confidence_aggregation!r} is not implemented"
        )

    @staticmethod
    def _rollup_validation_status(issues: list[StrategyScoreValidationIssue]) -> ValidationStatus:
        if any(issue.severity == "ERROR" for issue in issues):
            return ValidationStatus.INVALID
        if issues:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID
