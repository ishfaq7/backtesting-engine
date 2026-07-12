from datetime import datetime, timedelta, timezone

from btengine.analysis.funding_rate.config import FundingRateAnalysisConfig
from btengine.analysis.funding_rate.models import FundingRateObservation
from btengine.analysis.funding_rate.validation import FundingDataValidator

UTC = timezone.utc


def _obs(hour: int, rate: float | None = 0.0001) -> FundingRateObservation:
    return FundingRateObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), funding_rate=rate
    )


def test_well_formed_series_has_no_issues() -> None:
    observations = [_obs(h) for h in range(5)]
    assert FundingDataValidator().validate(observations) == []


def test_missing_value_is_flagged_as_warning() -> None:
    observations = [_obs(0), _obs(1, None)]
    issues = FundingDataValidator().validate(observations)
    assert any(i.severity == "WARNING" and "missing" in i.message for i in issues)


def test_naive_timestamp_is_flagged_as_error() -> None:
    observation = FundingRateObservation(timestamp=datetime(2024, 1, 1), funding_rate=0.0001)
    issues = FundingDataValidator().validate([observation])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


def test_duplicate_timestamp_is_flagged_as_error() -> None:
    observations = [_obs(0, 0.0001), _obs(0, 0.0002)]
    issues = FundingDataValidator().validate(observations)
    assert any(i.severity == "ERROR" and "duplicate" in i.message for i in issues)


def test_outliers_are_not_checked_when_threshold_unset() -> None:
    observations = [_obs(h, 0.0001) for h in range(10)] + [_obs(10, 10.0)]
    issues = FundingDataValidator().validate(observations)
    assert not any("outlier" in i.message for i in issues)


def test_outliers_are_flagged_when_threshold_configured() -> None:
    observations = [_obs(h, 0.0001) for h in range(10)] + [_obs(10, 10.0)]
    config = FundingRateAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = FundingDataValidator(config).validate(observations)
    assert any(i.severity == "WARNING" and "outlier" in i.message for i in issues)


def test_outlier_check_skips_when_fewer_than_two_values() -> None:
    config = FundingRateAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = FundingDataValidator(config).validate([_obs(0)])
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_when_stdev_is_zero() -> None:
    observations = [_obs(h, 0.0001) for h in range(5)]
    config = FundingRateAnalysisConfig(outlier_zscore_threshold=1.0)
    issues = FundingDataValidator(config).validate(observations)
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_ignores_missing_values() -> None:
    observations = [_obs(h, 0.0001) for h in range(5)] + [_obs(5, None)]
    config = FundingRateAnalysisConfig(outlier_zscore_threshold=1.0)
    issues = FundingDataValidator(config).validate(observations)
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_missing_values_without_flagging_them() -> None:
    values = [0.0001, 0.0002, 0.0003, 0.0004]
    observations = [_obs(h, v) for h, v in enumerate(values)] + [_obs(len(values), None)]
    config = FundingRateAnalysisConfig(outlier_zscore_threshold=3.0)
    issues = FundingDataValidator(config).validate(observations)
    outlier_issues = [i for i in issues if "outlier" in i.message]
    assert not any(i.timestamp == observations[-1].timestamp for i in outlier_issues)


def test_gaps_are_not_checked_when_expected_interval_unset() -> None:
    observations = [_obs(0), _obs(100)]
    issues = FundingDataValidator().validate(observations)
    assert not any("gap" in i.message for i in issues)


def test_gap_is_flagged_when_expected_interval_configured() -> None:
    observations = [_obs(0), _obs(100)]
    config = FundingRateAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = FundingDataValidator(config).validate(observations)
    assert any(i.severity == "WARNING" and "gap" in i.message for i in issues)


def test_no_gap_flagged_when_interval_is_within_expected() -> None:
    observations = [_obs(0), _obs(8)]
    config = FundingRateAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = FundingDataValidator(config).validate(observations)
    assert not any("gap" in i.message for i in issues)


def test_gap_check_sorts_out_of_order_observations() -> None:
    observations = [_obs(100), _obs(0)]
    config = FundingRateAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = FundingDataValidator(config).validate(observations)
    assert any("gap" in i.message for i in issues)
