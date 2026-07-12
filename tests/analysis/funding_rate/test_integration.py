from datetime import datetime, timedelta, timezone

from btengine.analysis.funding_rate.integration import (
    observations_from_feature_values,
    observations_from_funding_rates,
)
from btengine.data.schema import FundingRate
from btengine.features.base import FeatureValue

UTC = timezone.utc


def test_observations_from_feature_values_maps_timestamp_and_value() -> None:
    values = [
        FeatureValue(
            symbol="BTCUSDT", feature_name="funding_standard.funding_rate",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=0.0001,
        ),
        FeatureValue(
            symbol="BTCUSDT", feature_name="funding_standard.funding_rate",
            timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), value=0.0002,
        ),
    ]
    observations = observations_from_feature_values(values)
    assert [o.funding_rate for o in observations] == [0.0001, 0.0002]
    assert [o.timestamp for o in observations] == [v.timestamp for v in values]


def test_observations_from_feature_values_sorts_by_timestamp() -> None:
    values = [
        FeatureValue(
            symbol="BTCUSDT", feature_name="funding_standard.funding_rate",
            timestamp=datetime(2024, 1, 1, 1, tzinfo=UTC), value=0.0002,
        ),
        FeatureValue(
            symbol="BTCUSDT", feature_name="funding_standard.funding_rate",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC), value=0.0001,
        ),
    ]
    observations = observations_from_feature_values(values)
    assert [o.funding_rate for o in observations] == [0.0001, 0.0002]


def test_observations_from_feature_values_handles_empty_list() -> None:
    assert observations_from_feature_values([]) == []


def _funding_rate(hour: int, rate: float) -> FundingRate:
    return FundingRate(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        funding_rate=rate,
    )


def test_observations_from_funding_rates_maps_timestamp_and_value() -> None:
    records = [_funding_rate(0, 0.0001), _funding_rate(1, 0.0002)]
    observations = observations_from_funding_rates(records)
    assert [o.funding_rate for o in observations] == [0.0001, 0.0002]


def test_observations_from_funding_rates_sorts_by_timestamp() -> None:
    records = [_funding_rate(1, 0.0002), _funding_rate(0, 0.0001)]
    observations = observations_from_funding_rates(records)
    assert [o.funding_rate for o in observations] == [0.0001, 0.0002]


def test_observations_from_funding_rates_handles_empty_list() -> None:
    assert observations_from_funding_rates([]) == []
