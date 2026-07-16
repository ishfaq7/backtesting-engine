import pytest

from btengine.risk.checks.base import RiskValidationCheck
from btengine.risk.checks.builtin import (
    InvalidAccountBalanceCheck,
    InvalidExposureCheck,
    InvalidLeverageCheck,
    InvalidPortfolioStateCheck,
    MissingConfigurationCheck,
    StrategyVersionMismatchCheck,
    default_checks,
)
from btengine.risk.config import RiskEngineConfig, RiskProfile
from btengine.risk.context import RiskRequest
from tests.risk.conftest import (
    NOW,
    make_decision_context,
    make_market_data,
    make_portfolio,
    make_position,
    make_strategy_score,
)


def _request(
    config: RiskEngineConfig | None = None, *, portfolio=None, market_data=None,
    decision_context=None, score=None,
) -> RiskRequest:
    return RiskRequest(
        symbol="BTCUSDT", reference_time=NOW,
        decision_context=decision_context or make_decision_context(),
        score=score or make_strategy_score(), portfolio=portfolio or make_portfolio(),
        market_data=market_data, config=config or RiskEngineConfig(engine_version="v1"),
    )


def _full_profile_config() -> RiskEngineConfig:
    profile = RiskProfile(
        name="p", max_leverage=3.0, max_risk_per_trade_pct=0.02, max_daily_drawdown_pct=0.05,
        max_total_drawdown_pct=0.2, max_exposure_pct=0.5, max_capital_allocation_pct=0.25,
        max_margin_utilization_pct=0.8, max_portfolio_risk_pct=0.1,
    )
    return RiskEngineConfig(engine_version="v1", profiles={"p": profile}, active_profile="p")


def test_risk_validation_check_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        RiskValidationCheck()  # type: ignore[abstract]


def test_default_checks_have_unique_stable_names() -> None:
    names = [check.check_name for check in default_checks()]
    assert names == [
        "invalid_leverage", "invalid_portfolio_state", "invalid_account_balance",
        "invalid_exposure", "missing_configuration", "strategy_version_mismatch",
    ]
    assert len(set(names)) == len(names)


# --- InvalidLeverageCheck ----------------------------------------------------------


def test_invalid_leverage_flags_non_positive_leverage() -> None:
    portfolio = make_portfolio(positions=(make_position(leverage=0.0),))
    issues = InvalidLeverageCheck().run(_request(portfolio=portfolio))
    assert any(i.severity == "ERROR" and "invalid leverage" in i.message for i in issues)


def test_invalid_leverage_flags_nan_leverage() -> None:
    portfolio = make_portfolio(positions=(make_position(leverage=float("nan")),))
    issues = InvalidLeverageCheck().run(_request(portfolio=portfolio))
    assert len(issues) == 1


def test_invalid_leverage_ignores_none_leverage() -> None:
    portfolio = make_portfolio(positions=(make_position(leverage=None),))
    assert InvalidLeverageCheck().run(_request(portfolio=portfolio)) == []


def test_invalid_leverage_accepts_valid_leverage() -> None:
    portfolio = make_portfolio(positions=(make_position(leverage=5.0),))
    assert InvalidLeverageCheck().run(_request(portfolio=portfolio)) == []


# --- InvalidPortfolioStateCheck ------------------------------------------------------


def test_invalid_portfolio_state_flags_nan_cash() -> None:
    portfolio = make_portfolio(cash=float("nan"))
    issues = InvalidPortfolioStateCheck().run(_request(portfolio=portfolio))
    assert any("cash" in i.message for i in issues)


def test_invalid_portfolio_state_flags_infinite_equity() -> None:
    portfolio = make_portfolio(equity=float("inf"))
    issues = InvalidPortfolioStateCheck().run(_request(portfolio=portfolio))
    assert any("equity" in i.message for i in issues)


def test_invalid_portfolio_state_flags_nan_position_quantity() -> None:
    portfolio = make_portfolio(positions=(make_position(quantity=float("nan")),))
    issues = InvalidPortfolioStateCheck().run(_request(portfolio=portfolio))
    assert any("quantity or entry price" in i.message for i in issues)


def test_invalid_portfolio_state_flags_negative_entry_price() -> None:
    portfolio = make_portfolio(positions=(make_position(avg_entry_price=-1.0),))
    issues = InvalidPortfolioStateCheck().run(_request(portfolio=portfolio))
    assert any("negative avg_entry_price" in i.message for i in issues)


def test_invalid_portfolio_state_accepts_well_formed_portfolio() -> None:
    portfolio = make_portfolio(positions=(make_position(),))
    assert InvalidPortfolioStateCheck().run(_request(portfolio=portfolio)) == []


# --- InvalidAccountBalanceCheck --------------------------------------------------------


def test_invalid_account_balance_flags_zero_equity() -> None:
    issues = InvalidAccountBalanceCheck().run(_request(portfolio=make_portfolio(equity=0.0)))
    assert any("not positive" in i.message for i in issues)


def test_invalid_account_balance_flags_negative_equity() -> None:
    issues = InvalidAccountBalanceCheck().run(_request(portfolio=make_portfolio(equity=-100.0)))
    assert len(issues) == 1


def test_invalid_account_balance_skips_nan_equity() -> None:
    # NaN equity is InvalidPortfolioStateCheck's finding, not a double-report here
    issues = InvalidAccountBalanceCheck().run(_request(portfolio=make_portfolio(equity=float("nan"))))
    assert issues == []


def test_invalid_account_balance_accepts_positive_equity() -> None:
    assert InvalidAccountBalanceCheck().run(_request()) == []


# --- InvalidExposureCheck ----------------------------------------------------------------


def test_invalid_exposure_flags_nan_unrealized_pnl() -> None:
    portfolio = make_portfolio(positions=(make_position(unrealized_pnl=float("nan")),))
    issues = InvalidExposureCheck().run(_request(portfolio=portfolio))
    assert any("unrealized_pnl" in i.message for i in issues)


def test_invalid_exposure_flags_non_positive_market_price() -> None:
    issues = InvalidExposureCheck().run(_request(market_data=make_market_data(price=0.0)))
    assert any("invalid price" in i.message for i in issues)


def test_invalid_exposure_accepts_missing_market_data() -> None:
    assert InvalidExposureCheck().run(_request(market_data=None)) == []


def test_invalid_exposure_accepts_valid_inputs() -> None:
    portfolio = make_portfolio(positions=(make_position(),))
    assert InvalidExposureCheck().run(_request(portfolio=portfolio, market_data=make_market_data())) == []


# --- MissingConfigurationCheck ---------------------------------------------------------------


def test_missing_configuration_flags_no_active_profile() -> None:
    issues = MissingConfigurationCheck().run(_request())
    assert any(i.severity == "WARNING" and "no active risk profile" in i.message for i in issues)


def test_missing_configuration_flags_unset_limits_on_active_profile() -> None:
    profile = RiskProfile(name="p", max_leverage=3.0)  # everything else unset
    config = RiskEngineConfig(engine_version="v1", profiles={"p": profile}, active_profile="p")
    issues = MissingConfigurationCheck().run(_request(config))
    assert any("unset limits" in i.message and "max_exposure_pct" in i.message for i in issues)


def test_missing_configuration_no_issue_for_fully_configured_profile() -> None:
    assert MissingConfigurationCheck().run(_request(_full_profile_config())) == []


# --- StrategyVersionMismatchCheck ----------------------------------------------------------------


def test_strategy_version_mismatch_flags_unexpected_version() -> None:
    config = RiskEngineConfig(engine_version="v1", expected_strategy_version="v2")
    issues = StrategyVersionMismatchCheck().run(_request(config))
    assert any("does not match" in i.message for i in issues)


def test_strategy_version_mismatch_not_checked_without_expected_version() -> None:
    issues = StrategyVersionMismatchCheck().run(_request())
    assert not any("does not match" in i.message for i in issues)


def test_strategy_version_mismatch_flags_context_score_disagreement() -> None:
    issues = StrategyVersionMismatchCheck().run(
        _request(decision_context=make_decision_context("v1"), score=make_strategy_score("v2"))
    )
    assert any("disagrees" in i.message for i in issues)


def test_strategy_version_mismatch_no_issue_when_consistent() -> None:
    assert StrategyVersionMismatchCheck().run(_request()) == []
