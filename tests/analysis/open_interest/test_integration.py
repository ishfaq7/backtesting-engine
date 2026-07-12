from datetime import datetime, timedelta, timezone

from btengine.analysis.open_interest.integration import (
    observations_from_feature_values,
    observations_from_open_interest_records,
)
from btengine.data.schema import OpenInterest
from btengine.features.base import FeatureValue

UTC = timezone.utc


def test_observations_from_feature_values_maps_timestamp_and_value() -> None:
    values = [
        FeatureValue(
            symbol="BTCUSDT", feature_name="open_interest.open_interest",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=1_000_000.0,
        ),
        FeatureValue(
            symbol="BTCUSDT", feature_name="open_interest.open_interest",
            timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), value=1_010_000.0,
        ),
    ]
    observations = observations_from_feature_values(values)
    assert [o.open_interest for o in observations] == [1_000_000.0, 1_010_000.0]
    assert [o.timestamp for o in observations] == [v.timestamp for v in values]


def test_observations_from_feature_values_sorts_by_timestamp() -> None:
    values = [
        FeatureValue(
            symbol="BTCUSDT", feature_name="open_interest.open_interest",
            timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), value=1_010_000.0,
        ),
        FeatureValue(
            symbol="BTCUSDT", feature_name="open_interest.open_interest",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=1_000_000.0,
        ),
    ]
    observations = observations_from_feature_values(values)
    assert [o.open_interest for o in observations] == [1_000_000.0, 1_010_000.0]


def test_observations_from_feature_values_handles_empty_list() -> None:
    assert observations_from_feature_values([]) == []


def _open_interest(hour: int, oi: float) -> OpenInterest:
    return OpenInterest(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        open_interest=oi,
    )


def test_observations_from_open_interest_records_maps_timestamp_and_value() -> None:
    records = [_open_interest(0, 1_000_000.0), _open_interest(1, 1_010_000.0)]
    observations = observations_from_open_interest_records(records)
    assert [o.open_interest for o in observations] == [1_000_000.0, 1_010_000.0]


def test_observations_from_open_interest_records_sorts_by_timestamp() -> None:
    records = [_open_interest(1, 1_010_000.0), _open_interest(0, 1_000_000.0)]
    observations = observations_from_open_interest_records(records)
    assert [o.open_interest for o in observations] == [1_000_000.0, 1_010_000.0]


def test_observations_from_open_interest_records_handles_empty_list() -> None:
    assert observations_from_open_interest_records([]) == []
