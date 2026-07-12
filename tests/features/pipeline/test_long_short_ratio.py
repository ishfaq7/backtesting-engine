from datetime import datetime, timedelta, timezone

from btengine.data.schema import LongShortRatio
from btengine.features.pipeline.long_short_ratio import LongShortRatioFeatures

UTC = timezone.utc


def _ratio(hour: int, long_ratio: float) -> LongShortRatio:
    return LongShortRatio(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        long_account_ratio=long_ratio, short_account_ratio=1.0 - long_ratio,
    )


def test_module_name_defaults_to_global() -> None:
    assert LongShortRatioFeatures().module_name == "long_short_ratio_global"


def test_module_name_reflects_source_label() -> None:
    assert LongShortRatioFeatures(source_label="top_account").module_name == "long_short_ratio_top_account"


def test_compute_returns_empty_list_for_no_records() -> None:
    assert LongShortRatioFeatures().compute("BTCUSDT", []) == []


def test_compute_emits_raw_ratios_and_derived_ratio() -> None:
    records = [_ratio(0, 0.6)]
    features = LongShortRatioFeatures().compute("BTCUSDT", records)
    by_name = {f.feature_name: f.value for f in features}
    assert abs(by_name["long_short_ratio_global.long_account_ratio"] - 0.6) < 1e-9
    assert abs(by_name["long_short_ratio_global.short_account_ratio"] - 0.4) < 1e-9
    assert abs(by_name["long_short_ratio_global.long_short_ratio"] - 1.5) < 1e-9


def test_compute_emits_change() -> None:
    records = [_ratio(0, 0.5), _ratio(1, 0.6)]
    features = LongShortRatioFeatures().compute("BTCUSDT", records)
    change = next(f for f in features if f.feature_name == "long_short_ratio_global.long_short_ratio_change")
    assert change.value > 0


def test_compute_windows_are_reflected_in_feature_names() -> None:
    records = [_ratio(h, 0.5 + (h % 5) * 0.01) for h in range(40)]
    module = LongShortRatioFeatures(sma_window=5, zscore_window=10)
    features = module.compute("BTCUSDT", records)
    names = {f.feature_name for f in features}
    assert "long_short_ratio_global.long_short_ratio_sma_5" in names
    assert "long_short_ratio_global.long_short_ratio_zscore_10" in names


def test_compute_sorts_out_of_order_records_by_timestamp() -> None:
    records = [_ratio(1, 0.6), _ratio(0, 0.5)]
    features = LongShortRatioFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "long_short_ratio_global.long_account_ratio"]
    assert [round(f.value, 2) for f in raw] == [0.5, 0.6]
