import pytest

from btengine.risk.config import RiskEngineConfig
from btengine.risk.context import RiskRequest
from btengine.risk.modules.base import RiskModule
from btengine.risk.modules.builtin import (
    CapitalAllocationModule,
    DailyDrawdownProtectionModule,
    ExposureManagementModule,
    LeverageValidationModule,
    MarginValidationModule,
    MaxRiskValidationModule,
    PortfolioRiskModule,
    PositionSizingModule,
    TotalDrawdownProtectionModule,
    default_modules,
)
from tests.risk.conftest import NOW, make_decision_context, make_portfolio, make_strategy_score

ALL_MODULES = [
    (PositionSizingModule, "position_sizing"),
    (LeverageValidationModule, "leverage_validation"),
    (MaxRiskValidationModule, "max_risk_validation"),
    (DailyDrawdownProtectionModule, "daily_drawdown_protection"),
    (TotalDrawdownProtectionModule, "total_drawdown_protection"),
    (ExposureManagementModule, "exposure_management"),
    (CapitalAllocationModule, "capital_allocation"),
    (MarginValidationModule, "margin_validation"),
    (PortfolioRiskModule, "portfolio_risk"),
]


def _request() -> RiskRequest:
    return RiskRequest(
        symbol="BTCUSDT", reference_time=NOW, decision_context=make_decision_context(),
        score=make_strategy_score(), portfolio=make_portfolio(), market_data=None,
        config=RiskEngineConfig(engine_version="v1"),
    )


def test_risk_module_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        RiskModule()  # type: ignore[abstract]


@pytest.mark.parametrize("module_cls,expected_name", ALL_MODULES)
def test_module_name_and_default_version(module_cls, expected_name: str) -> None:
    module = module_cls()
    assert module.module_name == expected_name
    assert module.module_version == "unversioned"


@pytest.mark.parametrize("module_cls,expected_name", ALL_MODULES)
def test_module_accepts_custom_version(module_cls, expected_name: str) -> None:
    assert module_cls(version="v2").module_version == "v2"


@pytest.mark.parametrize("module_cls,expected_name", ALL_MODULES)
def test_module_evaluate_raises_not_implemented_error(module_cls, expected_name: str) -> None:
    with pytest.raises(NotImplementedError):
        module_cls().evaluate(_request())


def test_default_modules_returns_all_nine_in_stable_order() -> None:
    modules = default_modules()
    assert [module.module_name for module in modules] == [name for _, name in ALL_MODULES]


def test_default_modules_propagates_version() -> None:
    modules = default_modules(version="v3")
    assert all(module.module_version == "v3" for module in modules)
