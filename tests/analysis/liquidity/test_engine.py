import math
from datetime import datetime, timedelta, timezone

import pytest

from btengine.analysis.liquidity.config import AggregationMethod, LiquidityAnalysisConfig
from btengine.analysis.liquidity.engine import LiquidityAnalysisEngine
from btengine.analysis.liquidity.errors import LiquidityAnalysisError
from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)
from btengine.analysis.liquidity.stats import compute_bias, half_split_delta, zscore_of_latest

UTC = timezone.utc


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour)


def _liq(hour: int, long_: float | None, short_: float | None, exchange: str = "BINANCE") -> LiquidationObservation:
    return LiquidationObservation(
        timestamp=_ts(hour), exchange=exchange, long_liquidation_usd=long_, short_liquidation_usd=short_
    )


def _ratio(hour: int, long_: float | None, short_: float | None, exchange: str = "BINANCE") -> RatioObservation:
    return RatioObservation(
        timestamp=_ts(hour), exchange=exchange, long_account_ratio=long_, short_account_ratio=short_
    )


def _oi(hour: int, value: float | None, exchange: str = "BINANCE") -> OpenInterestObservation:
    return OpenInterestObservation(timestamp=_ts(hour), exchange=exchange, open_interest=value)


def _price(hour: int, value: float | None, exchange: str = "BINANCE") -> PriceObservation:
    return PriceObservation(timestamp=_ts(hour), exchange=exchange, close=value)


def _liquidation_series(n: int) -> list[LiquidationObservation]:
    return [_liq(h, 100.0 + h * 10, 50.0) for h in range(n)]


# --- basic errors ------------------------------------------------------------


def test_analyze_raises_on_empty_liquidations() -> None:
    with pytest.raises(LiquidityAnalysisError):
        LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=[])


def test_analyze_raises_when_all_liquidations_are_missing_values() -> None:
    liquidations = [_liq(0, None, None), _liq(1, None, None)]
    with pytest.raises(LiquidityAnalysisError):
        LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)


def test_analyze_uppercases_symbol() -> None:
    result = LiquidityAnalysisEngine().analyze("btcusdt", liquidations=_liquidation_series(5))
    assert result.symbol == "BTCUSDT"


# --- liquidation volumes / bias / event count --------------------------------


def test_analyze_computes_liquidation_volumes() -> None:
    liquidations = _liquidation_series(5)
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    expected_long = sum(100.0 + h * 10 for h in range(5))
    expected_short = 50.0 * 5
    assert result.long_liquidation_volume == expected_long
    assert result.short_liquidation_volume == expected_short
    assert result.total_liquidation_volume == expected_long + expected_short
    assert result.liquidation_event_count == 5
    assert result.sample_size == 5


def test_analyze_liquidation_bias_matches_compute_bias() -> None:
    liquidations = _liquidation_series(5)
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    expected = compute_bias(result.long_liquidation_volume, result.short_liquidation_volume)
    assert result.liquidation_bias == pytest.approx(expected)


def test_analyze_liquidation_bias_is_none_when_all_volumes_are_zero() -> None:
    liquidations = [_liq(h, 0.0, 0.0) for h in range(5)]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    assert result.liquidation_bias is None


def test_analyze_window_limits_liquidation_totals() -> None:
    liquidations = _liquidation_series(10)
    config = LiquidityAnalysisConfig(analysis_window=3, spike_window=3)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    expected_long = sum(100.0 + h * 10 for h in range(7, 10))  # last 3
    assert result.long_liquidation_volume == expected_long
    assert result.liquidation_event_count == 3


# --- liquidation intensity / abnormal spike -----------------------------------


def test_analyze_liquidation_intensity_matches_zscore_of_latest() -> None:
    liquidations = _liquidation_series(10)
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    totals = [100.0 + h * 10 + 50.0 for h in range(10)]
    expected = zscore_of_latest(totals)
    assert result.liquidation_intensity == pytest.approx(expected)


def test_analyze_is_abnormal_liquidation_none_when_threshold_unset() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(10))
    assert result.is_abnormal_liquidation is None


def test_analyze_is_abnormal_liquidation_true_when_threshold_exceeded() -> None:
    liquidations = [_liq(h, 100.0 + (h % 3), 50.0) for h in range(10)] + [_liq(10, 100_000.0, 0.0)]
    config = LiquidityAnalysisConfig(spike_zscore_threshold=1.0)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.is_abnormal_liquidation is True


def test_analyze_is_abnormal_liquidation_false_when_threshold_not_exceeded() -> None:
    liquidations = [_liq(h, 100.0 + (h % 3), 50.0) for h in range(10)] + [_liq(10, 100_000.0, 0.0)]
    config = LiquidityAnalysisConfig(spike_zscore_threshold=1_000_000.0)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.is_abnormal_liquidation is False


def test_analyze_is_abnormal_liquidation_none_when_intensity_uncomputable() -> None:
    config = LiquidityAnalysisConfig(spike_zscore_threshold=1.0)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=_liquidation_series(1))
    assert result.liquidation_intensity is None
    assert result.is_abnormal_liquidation is None


# --- positioning: long/short ratio, top trader bias ---------------------------


def test_analyze_long_short_ratio_is_none_without_global_ratio() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.long_short_ratio is None


def test_analyze_long_short_ratio_uses_latest_global_reading() -> None:
    ratios = [_ratio(h, 0.5, 0.5) for h in range(4)] + [_ratio(4, 0.75, 0.25)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), global_ratio=ratios
    )
    assert result.long_short_ratio == pytest.approx(3.0)


def test_analyze_long_short_ratio_none_when_latest_short_is_zero() -> None:
    ratios = [_ratio(0, 1.0, 0.0)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), global_ratio=ratios
    )
    assert result.long_short_ratio is None


def test_analyze_top_trader_biases_are_none_without_data() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.top_trader_account_bias is None
    assert result.top_trader_position_bias is None
    assert result.top_trader_bias is None


def test_analyze_top_trader_bias_prefers_position_over_account() -> None:
    account = [_ratio(0, 0.5, 0.5)]
    position = [_ratio(0, 0.9, 0.1)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5),
        top_trader_account_ratio=account, top_trader_position_ratio=position,
    )
    assert result.top_trader_account_bias == pytest.approx(0.0)
    assert result.top_trader_position_bias == pytest.approx(0.8)
    assert result.top_trader_bias == pytest.approx(0.8)


def test_analyze_top_trader_bias_falls_back_to_account_when_position_absent() -> None:
    account = [_ratio(0, 0.9, 0.1)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), top_trader_account_ratio=account
    )
    assert result.top_trader_bias == pytest.approx(0.8)


# --- market crowdedness --------------------------------------------------------


def test_analyze_market_crowdedness_is_none_without_global_ratio() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.market_crowdedness is None


def test_analyze_market_crowdedness_matches_zscore_of_bias_series() -> None:
    ratios = [_ratio(h, 0.5 + h * 0.02, 0.5 - h * 0.02) for h in range(10)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), global_ratio=ratios
    )
    biases = [compute_bias(0.5 + h * 0.02, 0.5 - h * 0.02) for h in range(10)]
    expected = zscore_of_latest(biases)
    assert result.market_crowdedness == pytest.approx(expected)


# --- market participation / open interest context -----------------------------


def test_analyze_market_participation_is_none_without_open_interest() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.market_participation is None
    assert result.current_open_interest is None


def test_analyze_market_participation_computes_pct_change_over_window() -> None:
    ois = [_oi(h, 1_000_000.0 + h * 10_000.0) for h in range(5)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), open_interest=ois
    )
    expected = (1_040_000.0 - 1_000_000.0) / 1_000_000.0 * 100
    assert result.market_participation == pytest.approx(expected)
    assert result.current_open_interest == 1_040_000.0


def test_analyze_market_participation_none_when_earliest_oi_is_zero() -> None:
    ois = [_oi(0, 0.0), _oi(1, 1_000_000.0)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), open_interest=ois
    )
    assert result.market_participation is None


def test_analyze_market_participation_none_with_single_reading() -> None:
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), open_interest=[_oi(0, 1_000_000.0)]
    )
    assert result.market_participation is None
    assert result.current_open_interest == 1_000_000.0


# --- price context --------------------------------------------------------------


def test_analyze_current_price_is_none_without_price_data() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.current_price is None


def test_analyze_current_price_uses_latest_reading() -> None:
    prices = [_price(h, 60_000.0 + h * 100) for h in range(5)]
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT", liquidations=_liquidation_series(5), price=prices
    )
    assert result.current_price == 60_400.0


# --- liquidity pressure / shift --------------------------------------------------


def test_analyze_liquidity_pressure_and_shift_none_without_open_interest() -> None:
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.liquidity_pressure is None
    assert result.liquidity_shift is None


def test_analyze_liquidity_pressure_matches_manual_computation() -> None:
    liquidations = _liquidation_series(5)  # totals: 150,160,170,180,190 = 850
    ois = [_oi(h, 1_000_000.0) for h in range(5)]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations, open_interest=ois)
    expected_pressure = 850.0 / 1_000_000.0
    assert result.liquidity_pressure == pytest.approx(expected_pressure)


def test_analyze_liquidity_shift_matches_half_split_delta_of_pressures() -> None:
    liquidations = _liquidation_series(5)
    ois = [_oi(h, 1_000_000.0) for h in range(5)]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations, open_interest=ois)
    totals = [100.0 + h * 10 + 50.0 for h in range(5)]
    pressures = [t / 1_000_000.0 for t in totals]
    expected_shift = half_split_delta(pressures)
    assert result.liquidity_shift == pytest.approx(expected_shift)


def test_analyze_liquidity_pressure_none_when_no_overlapping_timestamps() -> None:
    liquidations = _liquidation_series(5)
    ois = [_oi(h, 1_000_000.0) for h in range(100, 105)]  # disjoint timestamps
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations, open_interest=ois)
    assert result.liquidity_pressure is None
    assert result.liquidity_shift is None


# --- exchange comparison -----------------------------------------------------------


def test_analyze_exchange_liquidation_totals_per_exchange() -> None:
    liquidations = [
        _liq(0, 100.0, 50.0, exchange="BINANCE"),
        _liq(0, 200.0, 100.0, exchange="OKX"),
        _liq(1, 100.0, 50.0, exchange="BINANCE"),
    ]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    assert result.exchange_liquidation_totals == {"BINANCE": 300.0, "OKX": 300.0}


def test_analyze_exchange_liquidation_totals_respects_window() -> None:
    liquidations = [_liq(h, 100.0, 0.0, exchange="BINANCE") for h in range(10)]
    config = LiquidityAnalysisConfig(analysis_window=3, spike_window=3)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.exchange_liquidation_totals == {"BINANCE": 300.0}  # last 3 bars only


# --- confidence level -----------------------------------------------------------------


def test_analyze_confidence_level_reflects_data_sufficiency() -> None:
    config = LiquidityAnalysisConfig(analysis_window=50, spike_window=50)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=_liquidation_series(5))
    assert result.confidence_level == pytest.approx(5 / 50)


def test_analyze_confidence_level_capped_at_one() -> None:
    config = LiquidityAnalysisConfig(analysis_window=3, spike_window=3)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=_liquidation_series(10))
    assert result.confidence_level == 1.0


# --- cleaning: missing/invalid/duplicates/ordering --------------------------------------


def test_analyze_excludes_missing_liquidation_readings() -> None:
    liquidations = _liquidation_series(5) + [_liq(5, None, None)]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    assert result.sample_size == 5


def test_analyze_excludes_missing_ratio_and_oi_and_price_readings() -> None:
    result = LiquidityAnalysisEngine().analyze(
        "BTCUSDT",
        liquidations=_liquidation_series(5),
        global_ratio=[_ratio(0, None, None)],
        open_interest=[_oi(0, None)],
        price=[_price(0, None)],
    )
    assert result.long_short_ratio is None
    assert result.current_open_interest is None
    assert result.current_price is None


def test_analyze_duplicate_timestamp_and_exchange_keeps_last_given() -> None:
    timestamp_liquidations = [
        LiquidationObservation(timestamp=_ts(0), exchange="BINANCE", long_liquidation_usd=100.0, short_liquidation_usd=50.0),
        LiquidationObservation(timestamp=_ts(0), exchange="BINANCE", long_liquidation_usd=999.0, short_liquidation_usd=1.0),
    ]
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=timestamp_liquidations)
    assert result.long_liquidation_volume == 999.0
    assert result.sample_size == 1


def test_analyze_sorts_out_of_order_liquidations() -> None:
    liquidations = list(reversed(_liquidation_series(5)))
    result = LiquidityAnalysisEngine().analyze("BTCUSDT", liquidations=liquidations)
    assert result.as_of == _ts(4)


# --- exchange selection / aggregation method --------------------------------------------


def test_exchange_selection_filters_out_other_exchanges() -> None:
    liquidations = [_liq(0, 100.0, 50.0, exchange="BINANCE"), _liq(0, 500.0, 500.0, exchange="OKX")]
    config = LiquidityAnalysisConfig(exchange_selection=("BINANCE",))
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.long_liquidation_volume == 100.0
    assert result.exchange_liquidation_totals == {"BINANCE": 150.0}


def test_aggregation_method_sum_combines_same_timestamp_exchanges() -> None:
    liquidations = [_liq(0, 100.0, 0.0, exchange="BINANCE"), _liq(0, 200.0, 0.0, exchange="OKX")]
    config = LiquidityAnalysisConfig(aggregation_method=AggregationMethod.SUM)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.long_liquidation_volume == 300.0


def test_aggregation_method_mean_combines_same_timestamp_exchanges() -> None:
    liquidations = [_liq(0, 100.0, 0.0, exchange="BINANCE"), _liq(0, 200.0, 0.0, exchange="OKX")]
    config = LiquidityAnalysisConfig(aggregation_method=AggregationMethod.MEAN)
    result = LiquidityAnalysisEngine(config).analyze("BTCUSDT", liquidations=liquidations)
    assert result.long_liquidation_volume == 150.0


# --- validate() delegation --------------------------------------------------------------


def test_validate_delegates_to_liquidity_data_validator() -> None:
    naive = LiquidationObservation(
        timestamp=datetime(2024, 1, 1), exchange="BINANCE", long_liquidation_usd=1.0, short_liquidation_usd=1.0
    )
    issues = LiquidityAnalysisEngine().validate(liquidations=[naive])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)
