from datetime import datetime, timezone

from btengine.analysis.open_interest.models import OiDirection, OpenInterestAnalysis, OpenInterestObservation

UTC = timezone.utc


def test_open_interest_observation_allows_none_value() -> None:
    observation = OpenInterestObservation(timestamp=datetime(2024, 1, 1, tzinfo=UTC), open_interest=None)
    assert observation.open_interest is None


def _analysis(**overrides) -> OpenInterestAnalysis:
    defaults = dict(
        symbol="BTCUSDT",
        source="aggregated",
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        current_oi=1_000_000.0,
        previous_oi=990_000.0,
        oi_change=10_000.0,
        oi_change_pct=0.0101,
        oi_trend=OiDirection.RISING,
        oi_trend_value=500.0,
        oi_momentum=OiDirection.FLAT,
        oi_momentum_value=0.0,
        oi_volatility=1200.0,
        is_abnormal_spike=False,
        spike_magnitude=0.4,
        historical_average=980_000.0,
        historical_maximum=1_010_000.0,
        historical_minimum=950_000.0,
        sample_size=40,
        confidence_level=1.0,
    )
    defaults.update(overrides)
    return OpenInterestAnalysis(**defaults)


def test_to_feature_map_namespaces_by_source() -> None:
    analysis = _analysis(source="aggregated")
    feature_map = analysis.to_feature_map()
    assert "open_interest_analysis_aggregated.current_oi" in feature_map
    assert feature_map["open_interest_analysis_aggregated.current_oi"] == 1_000_000.0


def test_to_feature_map_namespaces_by_exchange_source() -> None:
    analysis = _analysis(source="binance")
    feature_map = analysis.to_feature_map()
    assert "open_interest_analysis_binance.current_oi" in feature_map


def test_to_feature_map_includes_boolean_spike_flag_as_float() -> None:
    analysis = _analysis(is_abnormal_spike=True)
    feature_map = analysis.to_feature_map()
    assert feature_map["open_interest_analysis_aggregated.is_abnormal_spike"] == 1.0


def test_to_feature_map_includes_false_spike_flag_as_zero() -> None:
    analysis = _analysis(is_abnormal_spike=False)
    feature_map = analysis.to_feature_map()
    assert feature_map["open_interest_analysis_aggregated.is_abnormal_spike"] == 0.0


def test_to_feature_map_omits_spike_flag_when_unclassified() -> None:
    analysis = _analysis(is_abnormal_spike=None)
    feature_map = analysis.to_feature_map()
    assert "open_interest_analysis_aggregated.is_abnormal_spike" not in feature_map


def test_to_feature_map_includes_zero_values() -> None:
    analysis = _analysis(oi_momentum_value=0.0)
    feature_map = analysis.to_feature_map()
    assert feature_map["open_interest_analysis_aggregated.oi_momentum_value"] == 0.0


def test_to_feature_map_omits_none_fields() -> None:
    analysis = _analysis(
        previous_oi=None, oi_change=None, oi_change_pct=None,
        oi_trend_value=None, oi_momentum_value=None, oi_volatility=None,
        is_abnormal_spike=None, spike_magnitude=None,
        historical_average=None, historical_maximum=None, historical_minimum=None,
    )
    feature_map = analysis.to_feature_map()
    assert feature_map == {
        "open_interest_analysis_aggregated.current_oi": 1_000_000.0,
        "open_interest_analysis_aggregated.confidence_level": 1.0,
    }
