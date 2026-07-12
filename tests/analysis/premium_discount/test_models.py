from datetime import datetime, timezone

from btengine.analysis.premium_discount.models import (
    CandleObservation,
    PremiumDiscountAnalysis,
    PremiumDiscountZone,
)

UTC = timezone.utc


def test_candle_observation_allows_none_fields() -> None:
    observation = CandleObservation(timestamp=datetime(2024, 1, 1, tzinfo=UTC), high=None, low=None, close=None)
    assert observation.high is None
    assert observation.low is None
    assert observation.close is None


def _analysis(**overrides) -> PremiumDiscountAnalysis:
    defaults = dict(
        symbol="BTCUSDT",
        timeframe="1h",
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        active_high=110.0,
        active_low=90.0,
        range_size=20.0,
        midpoint=100.0,
        current_price=105.0,
        current_price_position_pct=75.0,
        zone=PremiumDiscountZone.PREMIUM,
        premium_percentage=50.0,
        discount_percentage=0.0,
        sample_size=50,
        confidence_level=1.0,
    )
    defaults.update(overrides)
    return PremiumDiscountAnalysis(**defaults)


def test_to_feature_map_namespaces_by_timeframe() -> None:
    analysis = _analysis(timeframe="4h")
    feature_map = analysis.to_feature_map()
    assert "premium_discount_analysis_4h.active_high" in feature_map
    assert feature_map["premium_discount_analysis_4h.active_high"] == 110.0


def test_to_feature_map_one_hot_encodes_zone() -> None:
    analysis = _analysis(zone=PremiumDiscountZone.PREMIUM)
    feature_map = analysis.to_feature_map()
    assert feature_map["premium_discount_analysis_1h.zone_is_premium"] == 1.0
    assert feature_map["premium_discount_analysis_1h.zone_is_discount"] == 0.0
    assert feature_map["premium_discount_analysis_1h.zone_is_equilibrium"] == 0.0
    assert feature_map["premium_discount_analysis_1h.zone_is_above_range"] == 0.0
    assert feature_map["premium_discount_analysis_1h.zone_is_below_range"] == 0.0


def test_to_feature_map_one_hot_encodes_a_different_zone() -> None:
    analysis = _analysis(zone=PremiumDiscountZone.BELOW_RANGE)
    feature_map = analysis.to_feature_map()
    assert feature_map["premium_discount_analysis_1h.zone_is_below_range"] == 1.0
    assert feature_map["premium_discount_analysis_1h.zone_is_premium"] == 0.0


def test_to_feature_map_includes_zero_values() -> None:
    analysis = _analysis(discount_percentage=0.0)
    feature_map = analysis.to_feature_map()
    assert feature_map["premium_discount_analysis_1h.discount_percentage"] == 0.0


def test_to_feature_map_omits_none_fields() -> None:
    analysis = _analysis(premium_percentage=None, discount_percentage=None)
    feature_map = analysis.to_feature_map()
    assert "premium_discount_analysis_1h.premium_percentage" not in feature_map
    assert "premium_discount_analysis_1h.discount_percentage" not in feature_map
    assert feature_map["premium_discount_analysis_1h.active_high"] == 110.0
