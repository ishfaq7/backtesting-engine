from datetime import datetime, timedelta, timezone

from btengine.analysis.open_interest.config import OpenInterestAnalysisConfig
from btengine.analysis.open_interest.models import OpenInterestObservation
from btengine.analysis.open_interest.validation import OpenInterestDataValidator

UTC = timezone.utc


def _obs(hour: int, oi: float | None = 1_000_000.0) -> OpenInterestObservation:
    return OpenInterestObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour), open_interest=oi
    )


def test_well_formed_series_has_no_issues() -> None:
    observations = [_obs(h) for h in range(5)]
    assert OpenInterestDataValidator().validate(observations) == []


def test_missing_value_is_flagged_as_warning() -> None:
    observations = [_obs(0), _obs(1, None)]
    issues = OpenInterestDataValidator().validate(observations)
    assert any(i.severity == "WARNING" and "missing" in i.message for i in issues)


def test_naive_timestamp_is_flagged_as_error() -> None:
    observation = OpenInterestObservation(timestamp=datetime(2024, 1, 1), open_interest=1_000_000.0)
    issues = OpenInterestDataValidator().validate([observation])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


def test_duplicate_timestamp_is_flagged_as_error() -> None:
    observations = [_obs(0, 1_000_000.0), _obs(0, 1_100_000.0)]
    issues = OpenInterestDataValidator().validate(observations)
    assert any(i.severity == "ERROR" and "duplicate" in i.message for i in issues)


def test_outliers_are_not_checked_when_threshold_unset() -> None:
    observations = [_obs(h, 1_000_000.0) for h in range(10)] + [_obs(10, 1e12)]
    issues = OpenInterestDataValidator().validate(observations)
    assert not any("outlier" in i.message for i in issues)


def test_outliers_are_flagged_when_threshold_configured() -> None:
    observations = [_obs(h, 1_000_000.0) for h in range(10)] + [_obs(10, 1e12)]
    config = OpenInterestAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = OpenInterestDataValidator(config).validate(observations)
    assert any(i.severity == "WARNING" and "outlier" in i.message for i in issues)


def test_outlier_check_skips_when_fewer_than_two_values() -> None:
    config = OpenInterestAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = OpenInterestDataValidator(config).validate([_obs(0)])
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_when_stdev_is_zero() -> None:
    observations = [_obs(h, 1_000_000.0) for h in range(5)]
    config = OpenInterestAnalysisConfig(outlier_zscore_threshold=1.0)
    issues = OpenInterestDataValidator(config).validate(observations)
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_missing_values_without_flagging_them() -> None:
    values = [1_000_000.0, 1_010_000.0, 1_020_000.0, 1_030_000.0]
    observations = [_obs(h, v) for h, v in enumerate(values)] + [_obs(len(values), None)]
    config = OpenInterestAnalysisConfig(outlier_zscore_threshold=3.0)
    issues = OpenInterestDataValidator(config).validate(observations)
    outlier_issues = [i for i in issues if "outlier" in i.message]
    assert not any(i.timestamp == observations[-1].timestamp for i in outlier_issues)


def test_gaps_are_not_checked_when_expected_interval_unset() -> None:
    observations = [_obs(0), _obs(100)]
    issues = OpenInterestDataValidator().validate(observations)
    assert not any("gap" in i.message for i in issues)


def test_gap_is_flagged_when_expected_interval_configured() -> None:
    observations = [_obs(0), _obs(100)]
    config = OpenInterestAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = OpenInterestDataValidator(config).validate(observations)
    assert any(i.severity == "WARNING" and "gap" in i.message for i in issues)


def test_no_gap_flagged_when_interval_is_within_expected() -> None:
    observations = [_obs(0), _obs(8)]
    config = OpenInterestAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = OpenInterestDataValidator(config).validate(observations)
    assert not any("gap" in i.message for i in issues)


def test_gap_check_sorts_out_of_order_observations() -> None:
    observations = [_obs(100), _obs(0)]
    config = OpenInterestAnalysisConfig(expected_interval=timedelta(hours=8))
    issues = OpenInterestDataValidator(config).validate(observations)
    assert any("gap" in i.message for i in issues)
