from datetime import datetime, timedelta, timezone

from btengine.data.schema import FundingRate
from btengine.features.pipeline.funding import FundingFeatures

UTC = timezone.utc


def _funding(hour: int, rate: float) -> FundingRate:
    return FundingRate(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        funding_rate=rate,
    )


def test_module_name_defaults_to_standard() -> None:
    assert FundingFeatures().module_name == "funding_standard"


def test_module_name_reflects_source_label() -> None:
    assert FundingFeatures(source_label="oi_weighted").module_name == "funding_oi_weighted"


def test_compute_returns_empty_list_for_no_records() -> None:
    assert FundingFeatures().compute("BTCUSDT", []) == []


def test_compute_emits_raw_funding_rate() -> None:
    records = [_funding(h, 0.0001 * h) for h in range(3)]
    features = FundingFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "funding_standard.funding_rate"]
    assert [f.value for f in raw] == [0.0, 0.0001, 0.0002]


def test_compute_emits_funding_rate_change() -> None:
    records = [_funding(0, 0.0001), _funding(1, 0.0003)]
    features = FundingFeatures().compute("BTCUSDT", records)
    change = next(f for f in features if f.feature_name == "funding_standard.funding_rate_change")
    assert abs(change.value - 0.0002) < 1e-12


def test_compute_windows_are_reflected_in_feature_names() -> None:
    records = [_funding(h, 0.0001 * h) for h in range(40)]
    module = FundingFeatures(sma_window=5, zscore_window=10)
    features = module.compute("BTCUSDT", records)
    names = {f.feature_name for f in features}
    assert "funding_standard.funding_rate_sma_5" in names
    assert "funding_standard.funding_rate_zscore_10" in names


def test_compute_sorts_out_of_order_records_by_timestamp() -> None:
    records = [_funding(1, 0.0002), _funding(0, 0.0001)]
    features = FundingFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "funding_standard.funding_rate"]
    assert [f.value for f in raw] == [0.0001, 0.0002]


def test_compute_zscore_skips_when_std_is_zero() -> None:
    records = [_funding(h, 0.0001) for h in range(35)]
    module = FundingFeatures(zscore_window=5)
    features = module.compute("BTCUSDT", records)
    zscore = [f for f in features if f.feature_name == "funding_standard.funding_rate_zscore_5"]
    assert zscore == []
