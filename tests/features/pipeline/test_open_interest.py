from datetime import datetime, timedelta, timezone

from btengine.data.schema import OpenInterest
from btengine.features.pipeline.open_interest import OpenInterestFeatures

UTC = timezone.utc


def _oi(hour: int, value: float) -> OpenInterest:
    return OpenInterest(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        open_interest=value,
    )


def test_module_name_is_open_interest() -> None:
    assert OpenInterestFeatures().module_name == "open_interest"


def test_compute_returns_empty_list_for_no_records() -> None:
    assert OpenInterestFeatures().compute("BTCUSDT", []) == []


def test_compute_emits_raw_open_interest() -> None:
    records = [_oi(h, 1000.0 + h * 10) for h in range(3)]
    features = OpenInterestFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "open_interest.open_interest"]
    assert [f.value for f in raw] == [1000.0, 1010.0, 1020.0]


def test_compute_emits_oi_change_pct() -> None:
    records = [_oi(0, 1000.0), _oi(1, 1100.0)]
    features = OpenInterestFeatures().compute("BTCUSDT", records)
    change = next(f for f in features if f.feature_name == "open_interest.oi_change_pct")
    assert abs(change.value - 0.1) < 1e-9


def test_compute_windows_are_reflected_in_feature_names() -> None:
    records = [_oi(h, 1000.0 + h) for h in range(40)]
    module = OpenInterestFeatures(sma_window=5, roc_window=6, zscore_window=10)
    features = module.compute("BTCUSDT", records)
    names = {f.feature_name for f in features}
    assert "open_interest.oi_sma_5" in names
    assert "open_interest.oi_roc_6" in names
    assert "open_interest.oi_zscore_10" in names


def test_compute_sorts_out_of_order_records_by_timestamp() -> None:
    records = [_oi(1, 1100.0), _oi(0, 1000.0)]
    features = OpenInterestFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "open_interest.open_interest"]
    assert [f.value for f in raw] == [1000.0, 1100.0]
