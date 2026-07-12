from datetime import datetime, timedelta, timezone

from btengine.analysis.liquidity.config import LiquidityAnalysisConfig
from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)
from btengine.analysis.liquidity.validation import LiquidityDataValidator

UTC = timezone.utc


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(hours=hour)


def _liq(hour: int, long_: float | None = 100.0, short_: float | None = 50.0, exchange: str = "BINANCE") -> LiquidationObservation:
    return LiquidationObservation(
        timestamp=_ts(hour), exchange=exchange, long_liquidation_usd=long_, short_liquidation_usd=short_
    )


def _ratio(hour: int, long_: float | None = 0.6, short_: float | None = 0.4, exchange: str = "BINANCE") -> RatioObservation:
    return RatioObservation(
        timestamp=_ts(hour), exchange=exchange, long_account_ratio=long_, short_account_ratio=short_
    )


def _oi(hour: int, value: float | None = 1_000_000.0, exchange: str = "BINANCE") -> OpenInterestObservation:
    return OpenInterestObservation(timestamp=_ts(hour), exchange=exchange, open_interest=value)


def _price(hour: int, value: float | None = 65_000.0, exchange: str = "BINANCE") -> PriceObservation:
    return PriceObservation(timestamp=_ts(hour), exchange=exchange, close=value)


def test_well_formed_data_has_no_issues() -> None:
    issues = LiquidityDataValidator().validate(
        liquidations=[_liq(h) for h in range(5)],
        global_ratio=[_ratio(h) for h in range(5)],
        top_trader_account_ratio=[_ratio(h) for h in range(5)],
        top_trader_position_ratio=[_ratio(h) for h in range(5)],
        open_interest=[_oi(h) for h in range(5)],
        price=[_price(h) for h in range(5)],
    )
    assert issues == []


def test_empty_call_has_no_issues() -> None:
    assert LiquidityDataValidator().validate() == []


def test_missing_liquidation_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0), _liq(1, long_=None)])
    assert any(i.severity == "WARNING" and "missing liquidation data" in i.message for i in issues)


def test_missing_global_ratio_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(
        liquidations=[_liq(0)], global_ratio=[_ratio(0), _ratio(1, long_=None)]
    )
    assert any(i.severity == "WARNING" and "missing global_ratio data" in i.message for i in issues)


def test_missing_top_trader_account_ratio_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(
        liquidations=[_liq(0)], top_trader_account_ratio=[_ratio(0, short_=None)]
    )
    assert any("missing top_trader_account_ratio data" in i.message for i in issues)


def test_missing_top_trader_position_ratio_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(
        liquidations=[_liq(0)], top_trader_position_ratio=[_ratio(0, short_=None)]
    )
    assert any("missing top_trader_position_ratio data" in i.message for i in issues)


def test_missing_open_interest_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0)], open_interest=[_oi(0, value=None)])
    assert any("missing open interest data" in i.message for i in issues)


def test_missing_price_data_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0)], price=[_price(0, value=None)])
    assert any("missing price data" in i.message for i in issues)


def test_naive_timestamp_is_flagged_as_error() -> None:
    naive = LiquidationObservation(
        timestamp=datetime(2024, 1, 1), exchange="BINANCE", long_liquidation_usd=1.0, short_liquidation_usd=1.0
    )
    issues = LiquidityDataValidator().validate(liquidations=[naive])
    assert any(i.severity == "ERROR" and "timezone-aware" in i.message for i in issues)


def test_duplicate_timestamp_and_exchange_is_flagged() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0), _liq(0)])
    assert any(i.severity == "ERROR" and "duplicate" in i.message for i in issues)


def test_same_timestamp_different_exchange_is_not_a_duplicate() -> None:
    issues = LiquidityDataValidator().validate(
        liquidations=[_liq(0, exchange="BINANCE"), _liq(0, exchange="OKX")]
    )
    assert not any("duplicate" in i.message for i in issues)


def test_outliers_not_checked_when_threshold_unset() -> None:
    liquidations = [_liq(h, long_=100.0, short_=50.0) for h in range(10)] + [_liq(10, long_=1e9, short_=0.0)]
    issues = LiquidityDataValidator().validate(liquidations=liquidations)
    assert not any("outlier" in i.message for i in issues)


def test_outliers_flagged_when_threshold_configured() -> None:
    liquidations = [_liq(h, long_=100.0, short_=50.0) for h in range(10)] + [_liq(10, long_=1e9, short_=0.0)]
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = LiquidityDataValidator(config).validate(liquidations=liquidations)
    assert any(i.severity == "WARNING" and "outlier" in i.message for i in issues)


def test_ratio_outliers_flagged_when_threshold_configured() -> None:
    ratios = [_ratio(h, long_=0.5, short_=0.5) for h in range(10)] + [_ratio(10, long_=1_000_000.0, short_=0.5)]
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0)], global_ratio=ratios)
    assert any("outlier global_ratio long_account_ratio" in i.message for i in issues)


def test_open_interest_outliers_flagged_when_threshold_configured() -> None:
    ois = [_oi(h, value=1_000_000.0) for h in range(10)] + [_oi(10, value=1e12)]
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0)], open_interest=ois)
    assert any("outlier open interest" in i.message for i in issues)


def test_price_outliers_flagged_when_threshold_configured() -> None:
    prices = [_price(h, value=65_000.0) for h in range(10)] + [_price(10, value=1e9)]
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0)], price=prices)
    assert any("outlier price" in i.message for i in issues)


def test_outlier_check_skips_when_fewer_than_two_values() -> None:
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=2.0)
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0)])
    assert not any("outlier" in i.message for i in issues)


def test_outlier_check_skips_when_stdev_is_zero() -> None:
    liquidations = [_liq(h, long_=100.0, short_=50.0) for h in range(5)]
    config = LiquidityAnalysisConfig(outlier_zscore_threshold=1.0)
    issues = LiquidityDataValidator(config).validate(liquidations=liquidations)
    assert not any("outlier" in i.message for i in issues)


def test_gaps_not_checked_when_expected_interval_unset() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0), _liq(100)])
    assert not any("gap" in i.message for i in issues)


def test_gap_flagged_when_expected_interval_configured() -> None:
    config = LiquidityAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0), _liq(100)])
    assert any(i.severity == "WARNING" and "gap" in i.message for i in issues)


def test_no_gap_flagged_when_interval_within_expected() -> None:
    config = LiquidityAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0), _liq(1)])
    assert not any("gap" in i.message for i in issues)


def test_gap_check_is_scoped_per_exchange() -> None:
    # BINANCE has a large gap, OKX doesn't - only BINANCE should be flagged.
    liquidations = [
        _liq(0, exchange="BINANCE"), _liq(100, exchange="BINANCE"),
        _liq(0, exchange="OKX"), _liq(1, exchange="OKX"),
    ]
    config = LiquidityAnalysisConfig(expected_interval=timedelta(hours=1))
    issues = LiquidityDataValidator(config).validate(liquidations=liquidations)
    gap_issues = [i for i in issues if "gap" in i.message]
    assert len(gap_issues) == 1
    assert "BINANCE" in gap_issues[0].message


def test_exchange_consistency_not_checked_when_selection_unset() -> None:
    issues = LiquidityDataValidator().validate(liquidations=[_liq(0, exchange="BINANCE")])
    assert not any("not found" in i.message for i in issues)


def test_exchange_consistency_flags_selected_exchange_absent_from_data() -> None:
    config = LiquidityAnalysisConfig(exchange_selection=("OKX",))
    issues = LiquidityDataValidator(config).validate(liquidations=[_liq(0, exchange="BINANCE")])
    assert any(i.severity == "WARNING" and "OKX" in i.message and "not found" in i.message for i in issues)


def test_exchange_consistency_does_not_flag_a_selected_exchange_present_in_any_source() -> None:
    config = LiquidityAnalysisConfig(exchange_selection=("OKX",))
    issues = LiquidityDataValidator(config).validate(
        liquidations=[_liq(0, exchange="BINANCE")], open_interest=[_oi(0, exchange="OKX")]
    )
    assert not any("not found" in i.message for i in issues)
