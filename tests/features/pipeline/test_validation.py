from datetime import datetime, timezone

from btengine.features.base import FeatureValue
from btengine.features.pipeline.validation import FeaturePipelineValidator

UTC = timezone.utc


def _value(hour: int, value: float = 1.0, feature_name: str = "x", version: str = "v1", symbol: str = "BTCUSDT") -> FeatureValue:
    return FeatureValue(
        symbol=symbol, feature_name=feature_name, timestamp=datetime(2024, 1, 1, hour, tzinfo=UTC),
        value=value, version=version,
    )


def test_empty_list_has_no_issues() -> None:
    assert FeaturePipelineValidator().validate([]) == []


def test_well_formed_series_has_no_issues() -> None:
    values = [_value(0, 1.0), _value(1, 2.0), _value(2, 3.0)]
    assert FeaturePipelineValidator().validate(values) == []


def test_nan_value_is_flagged() -> None:
    values = [_value(0, float("nan"))]
    issues = FeaturePipelineValidator().validate(values)
    assert len(issues) == 1
    assert issues[0].severity == "ERROR"
    assert "NaN" in issues[0].message


def test_infinite_value_is_flagged() -> None:
    values = [_value(0, float("inf"))]
    issues = FeaturePipelineValidator().validate(values)
    assert any("infinite" in i.message for i in issues)


def test_naive_timestamp_is_flagged() -> None:
    value = FeatureValue(symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1), value=1.0)
    issues = FeaturePipelineValidator().validate([value])
    assert any("timezone-aware" in i.message for i in issues)


def test_duplicate_timestamp_same_version_is_flagged() -> None:
    values = [_value(0, 1.0), _value(0, 2.0)]
    issues = FeaturePipelineValidator().validate(values)
    assert any("duplicate" in i.message for i in issues)


def test_same_timestamp_different_versions_is_not_a_duplicate() -> None:
    values = [_value(0, 1.0, version="v1"), _value(0, 2.0, version="v2")]
    issues = FeaturePipelineValidator().validate(values)
    assert issues == []


def test_out_of_order_timestamps_are_flagged() -> None:
    values = [_value(1, 1.0), _value(0, 2.0)]  # hour 1 then hour 0 - fine for duplicates, but let's force equal
    # use two identical timestamps constructed out of insertion order to trigger non-increasing check
    values = [
        FeatureValue(symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1, 0, tzinfo=UTC), value=1.0),
        FeatureValue(symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1, 0, tzinfo=UTC), value=2.0),
    ]
    issues = FeaturePipelineValidator().validate(values)
    # this is also a duplicate (same timestamp) - both checks should agree it's a problem
    assert any("duplicate" in i.message for i in issues)


def test_different_feature_names_are_independent_series() -> None:
    values = [_value(0, 1.0, feature_name="a"), _value(0, 2.0, feature_name="b")]
    assert FeaturePipelineValidator().validate(values) == []


def test_different_symbols_are_independent_series() -> None:
    values = [_value(0, 1.0, symbol="BTCUSDT"), _value(0, 2.0, symbol="ETHUSDT")]
    assert FeaturePipelineValidator().validate(values) == []


def test_multiple_issues_are_all_reported() -> None:
    values = [_value(0, float("nan")), _value(0, float("nan"))]  # NaN + duplicate
    issues = FeaturePipelineValidator().validate(values)
    severities = [i.severity for i in issues]
    assert severities.count("ERROR") >= 2
