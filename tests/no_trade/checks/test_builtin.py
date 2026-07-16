import pytest

from btengine.no_trade.checks.base import NoTradeValidationCheck
from btengine.no_trade.checks.builtin import (
    ConflictingFiltersCheck,
    DuplicateFiltersCheck,
    InvalidDataCheck,
    MissingFilterInputsCheck,
    StrategyVersionMismatchCheck,
    default_checks,
)
from btengine.no_trade.config import NoTradeEngineConfig
from btengine.no_trade.context import NoTradeRequest
from btengine.scoring.models import StrategyScore
from tests.no_trade.conftest import (
    NOW,
    make_decision_context,
    make_market_data,
    make_portfolio,
    make_risk_assessment,
    make_strategy_score,
)


def _request(
    config: NoTradeEngineConfig | None = None, *, score=None, decision_context=None,
    risk_assessment=None, market_data=None, portfolio=None, funding=None,
) -> NoTradeRequest:
    return NoTradeRequest(
        symbol="BTCUSDT", reference_time=NOW,
        decision_context=decision_context or make_decision_context(),
        score=score or make_strategy_score(), risk_assessment=risk_assessment,
        funding=funding, open_interest=None, premium_discount=None, liquidity=None,
        market_data=market_data, portfolio=portfolio,
        config=config or NoTradeEngineConfig(engine_version="v1"),
    )


def test_no_trade_validation_check_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        NoTradeValidationCheck()  # type: ignore[abstract]


def test_default_checks_have_unique_stable_names() -> None:
    names = [check.check_name for check in default_checks()]
    assert names == [
        "missing_filter_inputs", "invalid_data", "conflicting_filters",
        "duplicate_filters", "strategy_version_mismatch",
    ]
    assert len(set(names)) == len(names)


# --- MissingFilterInputsCheck ---------------------------------------------------------


def test_missing_filter_inputs_flags_absent_analyses_and_state() -> None:
    issues = MissingFilterInputsCheck().run(_request(), ())
    messages = {i.message for i in issues}
    assert "funding analysis was not provided" in messages
    assert "risk_assessment was not provided" in messages
    assert "market_data was not provided" in messages
    assert "portfolio was not provided" in messages
    assert all(i.severity == "WARNING" for i in issues)


def test_missing_filter_inputs_does_not_flag_supplied_inputs() -> None:
    issues = MissingFilterInputsCheck().run(
        _request(risk_assessment=make_risk_assessment(), market_data=make_market_data(),
                 portfolio=make_portfolio()),
        (),
    )
    messages = {i.message for i in issues}
    assert "risk_assessment was not provided" not in messages
    assert "market_data was not provided" not in messages
    assert "portfolio was not provided" not in messages


# --- InvalidDataCheck ---------------------------------------------------------------------


def test_invalid_data_flags_empty_score_symbol() -> None:
    issues = InvalidDataCheck().run(_request(score=make_strategy_score(symbol="")), ())
    assert any("empty symbol" in i.message for i in issues)


def test_invalid_data_flags_naive_score_timestamp() -> None:
    from datetime import datetime

    good = make_strategy_score()
    naive = StrategyScore(
        symbol=good.symbol, as_of=datetime(2024, 1, 1), score_version=good.score_version,
        funding_score=None, oi_score=None, premium_discount_score=None, liquidity_score=None,
        total_score=None, confidence=good.confidence, feature_status={},
    )
    issues = InvalidDataCheck().run(_request(score=naive), ())
    assert any("timezone-aware" in i.message for i in issues)


def test_invalid_data_flags_invalid_analysis_confidence() -> None:
    from tests.decision.conftest import make_funding_analysis

    funding = make_funding_analysis(confidence_level=2.0)
    issues = InvalidDataCheck().run(_request(funding=funding), ())
    assert any("invalid confidence_level" in i.message for i in issues)


def test_invalid_data_flags_non_positive_market_price() -> None:
    issues = InvalidDataCheck().run(_request(market_data=make_market_data(price=0.0)), ())
    assert any("invalid price" in i.message for i in issues)


def test_invalid_data_flags_nan_portfolio_equity() -> None:
    issues = InvalidDataCheck().run(_request(portfolio=make_portfolio(equity=float("nan"))), ())
    assert any("portfolio equity" in i.message for i in issues)


def test_invalid_data_accepts_well_formed_inputs() -> None:
    issues = InvalidDataCheck().run(
        _request(market_data=make_market_data(), portfolio=make_portfolio()), ()
    )
    assert issues == []


# --- ConflictingFiltersCheck -----------------------------------------------------------------


def test_conflicting_filters_flags_enabled_but_unregistered_filter() -> None:
    config = NoTradeEngineConfig(engine_version="v1", enabled_filters=("time_filter",))
    issues = ConflictingFiltersCheck().run(_request(config), ())
    assert any(i.severity == "ERROR" and "time_filter" in i.message for i in issues)


def test_conflicting_filters_no_issue_when_registered() -> None:
    config = NoTradeEngineConfig(engine_version="v1", enabled_filters=("time_filter",))
    assert ConflictingFiltersCheck().run(_request(config), ("time_filter",)) == []


def test_conflicting_filters_not_checked_without_enabled_list() -> None:
    assert ConflictingFiltersCheck().run(_request(), ()) == []


# --- DuplicateFiltersCheck --------------------------------------------------------------------


def test_duplicate_filters_flags_repeated_registration() -> None:
    issues = DuplicateFiltersCheck().run(_request(), ("time_filter", "time_filter"))
    assert any(i.severity == "ERROR" and "more than once" in i.message for i in issues)


def test_duplicate_filters_reports_each_duplicate_once() -> None:
    issues = DuplicateFiltersCheck().run(
        _request(), ("time_filter", "time_filter", "time_filter")
    )
    assert len(issues) == 1


def test_duplicate_filters_no_issue_for_unique_names() -> None:
    assert DuplicateFiltersCheck().run(_request(), ("a", "b")) == []


# --- StrategyVersionMismatchCheck ----------------------------------------------------------------


def test_strategy_version_mismatch_flags_unexpected_version() -> None:
    config = NoTradeEngineConfig(engine_version="v1", expected_strategy_version="v2")
    issues = StrategyVersionMismatchCheck().run(_request(config), ())
    assert any("does not match" in i.message for i in issues)


def test_strategy_version_mismatch_flags_context_score_disagreement() -> None:
    issues = StrategyVersionMismatchCheck().run(
        _request(decision_context=make_decision_context("v1"), score=make_strategy_score("v2")), ()
    )
    assert any("StrategyScore.score_version" in i.message for i in issues)


def test_strategy_version_mismatch_flags_risk_assessment_disagreement() -> None:
    issues = StrategyVersionMismatchCheck().run(
        _request(risk_assessment=make_risk_assessment("v2")), ()
    )
    assert any("RiskAssessment.strategy_version" in i.message for i in issues)


def test_strategy_version_mismatch_no_issue_when_consistent() -> None:
    issues = StrategyVersionMismatchCheck().run(
        _request(risk_assessment=make_risk_assessment("v1")), ()
    )
    assert issues == []
