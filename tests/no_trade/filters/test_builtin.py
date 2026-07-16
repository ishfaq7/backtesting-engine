import pytest

from btengine.no_trade.config import NoTradeEngineConfig
from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.filters.base import NoTradeFilter
from btengine.no_trade.filters.builtin import (
    DataQualityFilter,
    ExchangeFilter,
    MarketConditionFilter,
    PortfolioFilter,
    RiskFilter,
    SessionFilter,
    StrategyFilter,
    TimeFilter,
    default_filters,
)
from tests.no_trade.conftest import NOW, make_decision_context, make_strategy_score

ALL_FILTERS = [
    (MarketConditionFilter, "market_condition_filter"),
    (RiskFilter, "risk_filter"),
    (StrategyFilter, "strategy_filter"),
    (PortfolioFilter, "portfolio_filter"),
    (DataQualityFilter, "data_quality_filter"),
    (TimeFilter, "time_filter"),
    (SessionFilter, "session_filter"),
    (ExchangeFilter, "exchange_filter"),
]


def _request() -> NoTradeRequest:
    return NoTradeRequest(
        symbol="BTCUSDT", reference_time=NOW, decision_context=make_decision_context(),
        score=make_strategy_score(), risk_assessment=None, funding=None, open_interest=None,
        premium_discount=None, liquidity=None, market_data=None, portfolio=None,
        config=NoTradeEngineConfig(engine_version="v1"),
    )


def test_no_trade_filter_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        NoTradeFilter()  # type: ignore[abstract]


@pytest.mark.parametrize("filter_cls,expected_name", ALL_FILTERS)
def test_filter_name_and_default_version(filter_cls, expected_name: str) -> None:
    no_trade_filter = filter_cls()
    assert no_trade_filter.filter_name == expected_name
    assert no_trade_filter.filter_version == "unversioned"


@pytest.mark.parametrize("filter_cls,expected_name", ALL_FILTERS)
def test_filter_accepts_custom_version(filter_cls, expected_name: str) -> None:
    assert filter_cls(version="v2").filter_version == "v2"


@pytest.mark.parametrize("filter_cls,expected_name", ALL_FILTERS)
def test_filter_evaluate_raises_not_implemented_error(filter_cls, expected_name: str) -> None:
    with pytest.raises(NotImplementedError):
        filter_cls().evaluate(_request())


def test_default_filters_returns_all_eight_in_stable_order() -> None:
    filters = default_filters()
    assert [f.filter_name for f in filters] == [name for _, name in ALL_FILTERS]


def test_default_filters_propagates_version() -> None:
    assert all(f.filter_version == "v3" for f in default_filters(version="v3"))
