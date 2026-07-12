from datetime import datetime, timezone

import pytest

from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection
from btengine.analysis.liquidity.models import LiquidityAnalysis
from btengine.analysis.open_interest.models import OiDirection, OpenInterestAnalysis
from btengine.analysis.premium_discount.models import PremiumDiscountAnalysis, PremiumDiscountZone
from btengine.scoring.providers.base import ScoreProvider
from btengine.scoring.providers.funding import FundingScoreProvider
from btengine.scoring.providers.liquidity import LiquidityScoreProvider
from btengine.scoring.providers.open_interest import OpenInterestScoreProvider
from btengine.scoring.providers.premium_discount import PremiumDiscountScoreProvider

UTC = timezone.utc


def test_score_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ScoreProvider()  # type: ignore[abstract]


def _funding_analysis() -> FundingAnalysis:
    return FundingAnalysis(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), current_funding=0.0001,
        previous_funding=0.0001, funding_change=0.0, funding_change_pct=0.0,
        funding_trend=FundingDirection.FLAT, funding_trend_value=0.0,
        funding_momentum=FundingDirection.FLAT, funding_momentum_value=0.0, funding_volatility=0.0,
        historical_average=0.0001, historical_maximum=0.0001, historical_minimum=0.0001,
        sample_size=30, confidence_level=1.0,
    )


def _oi_analysis() -> OpenInterestAnalysis:
    return OpenInterestAnalysis(
        symbol="BTCUSDT", source="aggregated", as_of=datetime(2024, 1, 1, tzinfo=UTC),
        current_oi=1_000_000.0, previous_oi=1_000_000.0, oi_change=0.0, oi_change_pct=0.0,
        oi_trend=OiDirection.FLAT, oi_trend_value=0.0, oi_momentum=OiDirection.FLAT,
        oi_momentum_value=0.0, oi_volatility=0.0, is_abnormal_spike=None, spike_magnitude=None,
        historical_average=1_000_000.0, historical_maximum=1_000_000.0, historical_minimum=1_000_000.0,
        sample_size=30, confidence_level=1.0,
    )


def _premium_discount_analysis() -> PremiumDiscountAnalysis:
    return PremiumDiscountAnalysis(
        symbol="BTCUSDT", timeframe="1h", as_of=datetime(2024, 1, 1, tzinfo=UTC),
        active_high=110.0, active_low=90.0, range_size=20.0, midpoint=100.0,
        current_price=100.0, current_price_position_pct=50.0, zone=PremiumDiscountZone.EQUILIBRIUM,
        premium_percentage=0.0, discount_percentage=0.0, sample_size=50, confidence_level=1.0,
    )


def _liquidity_analysis() -> LiquidityAnalysis:
    return LiquidityAnalysis(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), sample_size=30, confidence_level=1.0,
        long_liquidation_volume=1000.0, short_liquidation_volume=500.0, total_liquidation_volume=1500.0,
        liquidation_event_count=30, liquidation_bias=0.33, liquidation_intensity=None,
        is_abnormal_liquidation=None, long_short_ratio=None, top_trader_account_bias=None,
        top_trader_position_bias=None, top_trader_bias=None, market_crowdedness=None,
        market_participation=None, current_open_interest=None, current_price=None,
        liquidity_pressure=None, liquidity_shift=None,
    )


@pytest.mark.parametrize(
    "provider_cls,provider_name,analysis_factory",
    [
        (FundingScoreProvider, "funding", _funding_analysis),
        (OpenInterestScoreProvider, "open_interest", _oi_analysis),
        (PremiumDiscountScoreProvider, "premium_discount", _premium_discount_analysis),
        (LiquidityScoreProvider, "liquidity", _liquidity_analysis),
    ],
)
def test_provider_name_and_default_version(provider_cls, provider_name, analysis_factory) -> None:
    provider = provider_cls()
    assert provider.provider_name == provider_name
    assert provider.provider_version == "unversioned"


@pytest.mark.parametrize(
    "provider_cls,analysis_factory",
    [
        (FundingScoreProvider, _funding_analysis),
        (OpenInterestScoreProvider, _oi_analysis),
        (PremiumDiscountScoreProvider, _premium_discount_analysis),
        (LiquidityScoreProvider, _liquidity_analysis),
    ],
)
def test_provider_accepts_custom_version(provider_cls, analysis_factory) -> None:
    provider = provider_cls(version="v2")
    assert provider.provider_version == "v2"


@pytest.mark.parametrize(
    "provider_cls,analysis_factory",
    [
        (FundingScoreProvider, _funding_analysis),
        (OpenInterestScoreProvider, _oi_analysis),
        (PremiumDiscountScoreProvider, _premium_discount_analysis),
        (LiquidityScoreProvider, _liquidity_analysis),
    ],
)
def test_provider_compute_raises_not_implemented_error(provider_cls, analysis_factory) -> None:
    provider = provider_cls()
    with pytest.raises(NotImplementedError):
        provider.compute(analysis_factory())
