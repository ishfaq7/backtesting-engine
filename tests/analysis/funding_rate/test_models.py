from datetime import datetime, timezone

from btengine.analysis.funding_rate.models import FundingAnalysis, FundingDirection, FundingRateObservation

UTC = timezone.utc


def test_funding_rate_observation_allows_none_value() -> None:
    observation = FundingRateObservation(timestamp=datetime(2024, 1, 1, tzinfo=UTC), funding_rate=None)
    assert observation.funding_rate is None


def _analysis(**overrides) -> FundingAnalysis:
    defaults = dict(
        symbol="BTCUSDT",
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        current_funding=0.0001,
        previous_funding=0.00005,
        funding_change=0.00005,
        funding_change_pct=1.0,
        funding_trend=FundingDirection.RISING,
        funding_trend_value=0.00001,
        funding_momentum=FundingDirection.FLAT,
        funding_momentum_value=0.0,
        funding_volatility=0.00002,
        historical_average=0.00007,
        historical_maximum=0.0002,
        historical_minimum=0.00001,
        sample_size=10,
        confidence_level=0.8,
    )
    defaults.update(overrides)
    return FundingAnalysis(**defaults)


def test_to_feature_map_includes_every_numeric_field() -> None:
    analysis = _analysis()
    feature_map = analysis.to_feature_map()
    assert feature_map["funding_rate_analysis.current_funding"] == 0.0001
    assert feature_map["funding_rate_analysis.funding_trend_value"] == 0.00001
    assert feature_map["funding_rate_analysis.confidence_level"] == 0.8
    assert len(feature_map) == 11


def test_to_feature_map_includes_zero_values() -> None:
    analysis = _analysis(funding_momentum_value=0.0)
    feature_map = analysis.to_feature_map()
    assert feature_map["funding_rate_analysis.funding_momentum_value"] == 0.0


def test_to_feature_map_omits_none_fields() -> None:
    analysis = _analysis(
        previous_funding=None, funding_change=None, funding_change_pct=None,
        funding_trend_value=None, funding_momentum_value=None, funding_volatility=None,
        historical_average=None, historical_maximum=None, historical_minimum=None,
    )
    feature_map = analysis.to_feature_map()
    assert feature_map == {
        "funding_rate_analysis.current_funding": 0.0001,
        "funding_rate_analysis.confidence_level": 0.8,
    }
