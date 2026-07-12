from datetime import datetime, timezone

from btengine.analysis.liquidity.models import (
    LiquidationObservation,
    LiquidityAnalysis,
    OpenInterestObservation,
    PriceObservation,
    RatioObservation,
)

UTC = timezone.utc


def test_liquidation_observation_allows_none_fields() -> None:
    observation = LiquidationObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), exchange="BINANCE",
        long_liquidation_usd=None, short_liquidation_usd=None,
    )
    assert observation.long_liquidation_usd is None


def test_ratio_observation_allows_none_fields() -> None:
    observation = RatioObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), exchange="BINANCE",
        long_account_ratio=None, short_account_ratio=None,
    )
    assert observation.long_account_ratio is None


def test_open_interest_observation_allows_none_field() -> None:
    observation = OpenInterestObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), exchange="BINANCE", open_interest=None
    )
    assert observation.open_interest is None


def test_price_observation_allows_none_field() -> None:
    observation = PriceObservation(
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), exchange="BINANCE", close=None
    )
    assert observation.close is None


def _analysis(**overrides) -> LiquidityAnalysis:
    defaults = dict(
        symbol="BTCUSDT",
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        sample_size=30,
        confidence_level=1.0,
        long_liquidation_volume=1000.0,
        short_liquidation_volume=500.0,
        total_liquidation_volume=1500.0,
        liquidation_event_count=30,
        liquidation_bias=0.33,
        liquidation_intensity=1.2,
        is_abnormal_liquidation=False,
        long_short_ratio=1.5,
        top_trader_account_bias=0.1,
        top_trader_position_bias=0.2,
        top_trader_bias=0.2,
        market_crowdedness=0.5,
        market_participation=5.0,
        current_open_interest=1_000_000.0,
        current_price=65_000.0,
        liquidity_pressure=0.02,
        liquidity_shift=0.001,
        exchange_liquidation_totals={"BINANCE": 1200.0, "OKX": 300.0},
    )
    defaults.update(overrides)
    return LiquidityAnalysis(**defaults)


def test_to_feature_map_includes_numeric_fields() -> None:
    analysis = _analysis()
    feature_map = analysis.to_feature_map()
    assert feature_map["liquidity_analysis.long_liquidation_volume"] == 1000.0
    assert feature_map["liquidity_analysis.liquidation_bias"] == 0.33
    assert feature_map["liquidity_analysis.confidence_level"] == 1.0


def test_to_feature_map_flattens_exchange_totals() -> None:
    analysis = _analysis()
    feature_map = analysis.to_feature_map()
    assert feature_map["liquidity_analysis.exchange_liquidation_total.BINANCE"] == 1200.0
    assert feature_map["liquidity_analysis.exchange_liquidation_total.OKX"] == 300.0


def test_to_feature_map_includes_abnormal_liquidation_as_float() -> None:
    analysis = _analysis(is_abnormal_liquidation=True)
    feature_map = analysis.to_feature_map()
    assert feature_map["liquidity_analysis.is_abnormal_liquidation"] == 1.0


def test_to_feature_map_includes_false_abnormal_liquidation_as_zero() -> None:
    analysis = _analysis(is_abnormal_liquidation=False)
    feature_map = analysis.to_feature_map()
    assert feature_map["liquidity_analysis.is_abnormal_liquidation"] == 0.0


def test_to_feature_map_omits_abnormal_liquidation_when_unclassified() -> None:
    analysis = _analysis(is_abnormal_liquidation=None)
    feature_map = analysis.to_feature_map()
    assert "liquidity_analysis.is_abnormal_liquidation" not in feature_map


def test_to_feature_map_omits_none_fields() -> None:
    analysis = _analysis(
        liquidation_bias=None, liquidation_intensity=None, long_short_ratio=None,
        top_trader_account_bias=None, top_trader_position_bias=None, top_trader_bias=None,
        market_crowdedness=None, market_participation=None, current_open_interest=None,
        current_price=None, liquidity_pressure=None, liquidity_shift=None,
        exchange_liquidation_totals={},
    )
    feature_map = analysis.to_feature_map()
    assert "liquidity_analysis.liquidation_bias" not in feature_map
    assert "liquidity_analysis.current_price" not in feature_map
    assert feature_map["liquidity_analysis.long_liquidation_volume"] == 1000.0


def test_to_feature_map_includes_zero_values() -> None:
    analysis = _analysis(liquidation_bias=0.0, market_participation=0.0)
    feature_map = analysis.to_feature_map()
    assert feature_map["liquidity_analysis.liquidation_bias"] == 0.0
    assert feature_map["liquidity_analysis.market_participation"] == 0.0


def test_exchange_liquidation_totals_defaults_to_empty_dict() -> None:
    defaults = dict(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), sample_size=1, confidence_level=1.0,
        long_liquidation_volume=1.0, short_liquidation_volume=1.0, total_liquidation_volume=2.0,
        liquidation_event_count=1, liquidation_bias=None, liquidation_intensity=None,
        is_abnormal_liquidation=None, long_short_ratio=None, top_trader_account_bias=None,
        top_trader_position_bias=None, top_trader_bias=None, market_crowdedness=None,
        market_participation=None, current_open_interest=None, current_price=None,
        liquidity_pressure=None, liquidity_shift=None,
    )
    analysis = LiquidityAnalysis(**defaults)
    assert analysis.exchange_liquidation_totals == {}
