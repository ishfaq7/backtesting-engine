from datetime import datetime, timedelta, timezone

from btengine.data.schema import Liquidation
from btengine.features.pipeline.liquidation import LiquidationFeatures

UTC = timezone.utc


def _liq(hour: int, long_usd: float, short_usd: float) -> Liquidation:
    return Liquidation(
        exchange="binance", symbol="btcusdt",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour),
        long_liquidation_usd=long_usd, short_liquidation_usd=short_usd,
    )


def test_module_name_is_liquidation() -> None:
    assert LiquidationFeatures().module_name == "liquidation"


def test_compute_returns_empty_list_for_no_records() -> None:
    assert LiquidationFeatures().compute("BTCUSDT", []) == []


def test_compute_emits_total_liquidation_usd() -> None:
    records = [_liq(0, 100.0, 50.0)]
    features = LiquidationFeatures().compute("BTCUSDT", records)
    total = next(f for f in features if f.feature_name == "liquidation.total_liquidation_usd")
    assert total.value == 150.0


def test_compute_emits_liquidation_imbalance() -> None:
    records = [_liq(0, 150.0, 50.0)]
    features = LiquidationFeatures().compute("BTCUSDT", records)
    imbalance = next(f for f in features if f.feature_name == "liquidation.liquidation_imbalance")
    assert abs(imbalance.value - 0.5) < 1e-9


def test_compute_skips_imbalance_when_both_sides_are_zero() -> None:
    records = [_liq(0, 0.0, 0.0)]
    features = LiquidationFeatures().compute("BTCUSDT", records)
    imbalance = [f for f in features if f.feature_name == "liquidation.liquidation_imbalance"]
    assert imbalance == []


def test_compute_rolling_window_reflected_in_feature_names() -> None:
    records = [_liq(h, 10.0, 5.0) for h in range(30)]
    module = LiquidationFeatures(rolling_window=5)
    features = module.compute("BTCUSDT", records)
    names = {f.feature_name for f in features}
    assert "liquidation.long_liquidation_usd_sum_5" in names
    assert "liquidation.short_liquidation_usd_sum_5" in names
    assert "liquidation.total_liquidation_usd_sum_5" in names


def test_compute_rolling_sum_values() -> None:
    records = [_liq(h, 10.0, 0.0) for h in range(5)]
    module = LiquidationFeatures(rolling_window=3)
    features = module.compute("BTCUSDT", records)
    sums = [f.value for f in features if f.feature_name == "liquidation.long_liquidation_usd_sum_3"]
    assert sums == [30.0, 30.0, 30.0]


def test_compute_sorts_out_of_order_records_by_timestamp() -> None:
    records = [_liq(1, 20.0, 0.0), _liq(0, 10.0, 0.0)]
    features = LiquidationFeatures().compute("BTCUSDT", records)
    raw = [f for f in features if f.feature_name == "liquidation.long_liquidation_usd"]
    assert [f.value for f in raw] == [10.0, 20.0]
