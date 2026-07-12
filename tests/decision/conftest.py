from datetime import datetime, timezone

from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OiDirection, OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis, PremiumDiscountZone
from btengine.scoring.models import FeatureStatus, StrategyScore
from btengine.signal_validation.models import (
    ConfidenceStatus,
    DataIntegrityStatus,
    FeatureCompleteness,
    ValidatedStrategyState,
)

UTC = timezone.utc


def make_funding_analysis(
    symbol: str = "BTCUSDT", as_of: datetime | None = None, confidence_level: float = 1.0
) -> FundingAnalysis:
    return FundingAnalysis(
        symbol=symbol, as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC), current_funding=0.0001,
        previous_funding=0.0001, funding_change=0.0, funding_change_pct=0.0,
        funding_trend=FundingDirection.FLAT, funding_trend_value=0.0,
        funding_momentum=FundingDirection.FLAT, funding_momentum_value=0.0, funding_volatility=0.0,
        historical_average=0.0001, historical_maximum=0.0001, historical_minimum=0.0001,
        sample_size=30, confidence_level=confidence_level,
    )


def make_oi_analysis(
    symbol: str = "BTCUSDT", as_of: datetime | None = None, confidence_level: float = 1.0
) -> OpenInterestAnalysis:
    return OpenInterestAnalysis(
        symbol=symbol, source="aggregated", as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC),
        current_oi=1_000_000.0, previous_oi=1_000_000.0, oi_change=0.0, oi_change_pct=0.0,
        oi_trend=OiDirection.FLAT, oi_trend_value=0.0, oi_momentum=OiDirection.FLAT,
        oi_momentum_value=0.0, oi_volatility=0.0, is_abnormal_spike=None, spike_magnitude=None,
        historical_average=1_000_000.0, historical_maximum=1_000_000.0, historical_minimum=1_000_000.0,
        sample_size=30, confidence_level=confidence_level,
    )


def make_premium_discount_analysis(
    symbol: str = "BTCUSDT", as_of: datetime | None = None, confidence_level: float = 1.0
) -> PremiumDiscountAnalysis:
    return PremiumDiscountAnalysis(
        symbol=symbol, timeframe="1h", as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC),
        active_high=110.0, active_low=90.0, range_size=20.0, midpoint=100.0,
        current_price=100.0, current_price_position_pct=50.0, zone=PremiumDiscountZone.EQUILIBRIUM,
        premium_percentage=0.0, discount_percentage=0.0, sample_size=50, confidence_level=confidence_level,
    )


def make_liquidity_analysis(
    symbol: str = "BTCUSDT", as_of: datetime | None = None, confidence_level: float = 1.0
) -> LiquidityAnalysis:
    return LiquidityAnalysis(
        symbol=symbol, as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC), sample_size=30,
        confidence_level=confidence_level, long_liquidation_volume=1000.0, short_liquidation_volume=500.0,
        total_liquidation_volume=1500.0, liquidation_event_count=30, liquidation_bias=0.33,
        liquidation_intensity=None, is_abnormal_liquidation=None, long_short_ratio=None,
        top_trader_account_bias=None, top_trader_position_bias=None, top_trader_bias=None,
        market_crowdedness=None, market_participation=None, current_open_interest=None,
        current_price=None, liquidity_pressure=None, liquidity_shift=None,
    )


def make_strategy_score(
    symbol: str = "BTCUSDT",
    as_of: datetime | None = None,
    score_version: str = "v1",
    confidence: float | None = 1.0,
    feature_status: dict[str, FeatureStatus] | None = None,
) -> StrategyScore:
    return StrategyScore(
        symbol=symbol, as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC), score_version=score_version,
        funding_score=None, oi_score=None, premium_discount_score=None, liquidity_score=None,
        total_score=None, confidence=confidence,
        feature_status=(
            feature_status
            if feature_status is not None
            else {
                "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.AVAILABLE,
                "premium_discount": FeatureStatus.AVAILABLE, "liquidity": FeatureStatus.AVAILABLE,
            }
        ),
    )


def make_validated_strategy_state(
    symbol: str = "BTCUSDT",
    as_of: datetime | None = None,
    strategy_version: str = "v1",
    score: StrategyScore | None = None,
    validation_passed: bool = True,
) -> ValidatedStrategyState:
    resolved_as_of = as_of or datetime(2024, 1, 1, tzinfo=UTC)
    resolved_score = score or make_strategy_score(symbol=symbol, as_of=resolved_as_of, score_version=strategy_version)
    return ValidatedStrategyState(
        symbol=symbol, as_of=resolved_as_of, strategy_version=strategy_version, score=resolved_score,
        validation_passed=validation_passed, validation_errors=(), validation_warnings=(),
        confidence_status=ConfidenceStatus.VALID,
        feature_completeness=FeatureCompleteness((), (), 1.0, None),
        module_health={}, data_integrity=DataIntegrityStatus.VALID,
    )
