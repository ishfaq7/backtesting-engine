from datetime import datetime, timezone

from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OiDirection, OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis, PremiumDiscountZone
from btengine.scoring.models import FeatureStatus, ScoreComponent, StrategyScore

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


def make_score_component(
    provider_name: str, value: float | None = 0.5, version: str = "v1", confidence: float | None = 1.0
) -> ScoreComponent:
    return ScoreComponent(
        provider_name=provider_name, provider_version=version, value=value, weight=1.0, confidence=confidence
    )


def make_strategy_score(
    symbol: str = "BTCUSDT",
    as_of: datetime | None = None,
    score_version: str = "v1",
    confidence: float | None = 1.0,
    feature_status: dict[str, FeatureStatus] | None = None,
    funding_score: ScoreComponent | None = None,
    oi_score: ScoreComponent | None = None,
    premium_discount_score: ScoreComponent | None = None,
    liquidity_score: ScoreComponent | None = None,
) -> StrategyScore:
    return StrategyScore(
        symbol=symbol, as_of=as_of or datetime(2024, 1, 1, tzinfo=UTC), score_version=score_version,
        funding_score=funding_score, oi_score=oi_score, premium_discount_score=premium_discount_score,
        liquidity_score=liquidity_score, total_score=None, confidence=confidence,
        feature_status=(
            feature_status
            if feature_status is not None
            else {
                "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.AVAILABLE,
                "premium_discount": FeatureStatus.AVAILABLE, "liquidity": FeatureStatus.AVAILABLE,
            }
        ),
    )
