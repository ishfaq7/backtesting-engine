import pytest

from btengine.risk.checks.base import RiskValidationCheck
from btengine.risk.config import RiskEngineConfig
from btengine.risk.context import RiskRequest
from btengine.risk.engine import RiskEngine
from btengine.risk.models import ExposureStatus, RiskModuleResult, RiskValidationIssue
from btengine.risk.modules.base import RiskModule
from btengine.risk.modules.builtin import default_modules
from btengine.scoring.models import ValidationStatus
from tests.risk.conftest import (
    NOW,
    make_decision_context,
    make_portfolio,
    make_strategy_score,
)


def _assess(engine: RiskEngine, *, portfolio=None):
    return engine.assess(
        "btcusdt", NOW, decision_context=make_decision_context(), score=make_strategy_score(),
        portfolio=portfolio or make_portfolio(),
    )


class _StubModule(RiskModule):
    def __init__(self, name: str, *, approved: bool | None, value: float | None = None) -> None:
        self._name = name
        self._approved = approved
        self._value = value

    @property
    def module_name(self) -> str:
        return self._name

    @property
    def module_version(self) -> str:
        return "v1"

    def evaluate(self, request: RiskRequest) -> RiskModuleResult:
        return RiskModuleResult(
            module_name=self._name, module_version="v1", approved=self._approved,
            value=self._value, reason="stub",
        )


def test_assess_uppercases_symbol() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"))
    assert _assess(engine).symbol == "BTCUSDT"


def test_assess_carries_as_of_and_strategy_version_from_decision_context() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"))
    result = _assess(engine)
    assert result.as_of == NOW
    assert result.strategy_version == "v1"
    assert result.timestamp == NOW


# --- fail-safe semantics -----------------------------------------------------------


def test_no_modules_registered_never_approves() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"))
    result = _assess(engine)
    assert result.risk_approved is False
    assert result.module_results == ()


def test_framework_only_modules_never_approve() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=default_modules())
    result = _assess(engine)
    assert result.risk_approved is False
    assert len(result.module_results) == 9
    assert all(r.approved is None for r in result.module_results)
    assert all(r.reason == "risk rule not implemented" for r in result.module_results)


def test_all_numeric_outputs_stay_none_with_framework_only_modules() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=default_modules())
    result = _assess(engine)
    assert result.position_size is None
    assert result.leverage_allowed is None
    assert result.max_risk_allowed is None
    assert result.portfolio_risk is None
    assert result.exposure_status == ExposureStatus.UNKNOWN


def test_unevaluated_module_blocks_approval_even_alongside_approving_ones() -> None:
    modules = [_StubModule("a", approved=True), _StubModule("b", approved=None)]
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=modules)
    assert _assess(engine).risk_approved is False


def test_explicit_rejection_blocks_approval() -> None:
    modules = [_StubModule("a", approved=True), _StubModule("b", approved=False)]
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=modules)
    assert _assess(engine).risk_approved is False


def test_all_modules_approving_yields_risk_approved() -> None:
    modules = [_StubModule("a", approved=True), _StubModule("b", approved=True)]
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=modules)
    assert _assess(engine).risk_approved is True


def test_validation_error_blocks_approval_and_skips_modules() -> None:
    modules = [_StubModule("a", approved=True)]
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=modules)
    result = _assess(engine, portfolio=make_portfolio(equity=-1.0))
    assert result.risk_approved is False
    assert result.validation_status == ValidationStatus.INVALID
    assert result.module_results == ()  # modules never ran on invalid input


# --- module value mapping ------------------------------------------------------------


def test_module_values_map_to_assessment_fields() -> None:
    modules = [
        _StubModule("position_sizing", approved=True, value=1.5),
        _StubModule("leverage_validation", approved=True, value=3.0),
        _StubModule("max_risk_validation", approved=True, value=0.02),
        _StubModule("portfolio_risk", approved=True, value=0.08),
    ]
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), modules=modules)
    result = _assess(engine)
    assert result.position_size == 1.5
    assert result.leverage_allowed == 3.0
    assert result.max_risk_allowed == 0.02
    assert result.portfolio_risk == 0.08


def test_unknown_module_name_maps_to_no_field() -> None:
    engine = RiskEngine(
        RiskEngineConfig(engine_version="v1"), modules=[_StubModule("custom", approved=True, value=9.9)]
    )
    result = _assess(engine)
    assert result.position_size is None
    assert result.risk_approved is True


# --- exposure status ---------------------------------------------------------------------


def test_exposure_status_within_limits_when_module_approves() -> None:
    engine = RiskEngine(
        RiskEngineConfig(engine_version="v1"),
        modules=[_StubModule("exposure_management", approved=True)],
    )
    assert _assess(engine).exposure_status == ExposureStatus.WITHIN_LIMITS


def test_exposure_status_exceeded_when_module_rejects() -> None:
    engine = RiskEngine(
        RiskEngineConfig(engine_version="v1"),
        modules=[_StubModule("exposure_management", approved=False)],
    )
    assert _assess(engine).exposure_status == ExposureStatus.EXCEEDED


def test_exposure_status_unknown_when_module_cannot_evaluate() -> None:
    engine = RiskEngine(
        RiskEngineConfig(engine_version="v1"),
        modules=[_StubModule("exposure_management", approved=None)],
    )
    assert _assess(engine).exposure_status == ExposureStatus.UNKNOWN


# --- validation status rollup ----------------------------------------------------------------


def test_validation_status_warning_with_only_warnings() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"))
    result = _assess(engine)  # no active profile -> configuration WARNING
    assert result.validation_status == ValidationStatus.WARNING
    assert len(result.warnings) == 1


def test_validation_status_valid_with_no_issues() -> None:
    from btengine.risk.config import RiskProfile

    profile = RiskProfile(
        name="p", max_leverage=3.0, max_risk_per_trade_pct=0.02, max_daily_drawdown_pct=0.05,
        max_total_drawdown_pct=0.2, max_exposure_pct=0.5, max_capital_allocation_pct=0.25,
        max_margin_utilization_pct=0.8, max_portfolio_risk_pct=0.1,
    )
    config = RiskEngineConfig(engine_version="v1", profiles={"p": profile}, active_profile="p")
    engine = RiskEngine(config)
    result = _assess(engine)
    assert result.validation_status == ValidationStatus.VALID


# --- metadata / DI ------------------------------------------------------------------------------


def test_metadata_lists_registered_modules_and_profile() -> None:
    engine = RiskEngine(
        RiskEngineConfig(engine_version="v2"), modules=[_StubModule("custom", approved=None)]
    )
    result = _assess(engine)
    assert result.metadata["registered_modules"] == ["custom"]
    assert result.metadata["engine_version"] == "v2"
    assert result.metadata["active_profile"] is None


class _AlwaysFailsCheck(RiskValidationCheck):
    @property
    def check_name(self) -> str:
        return "always_fails"

    def run(self, request) -> list[RiskValidationIssue]:
        return [RiskValidationIssue("ERROR", "custom", "custom failure")]


def test_custom_checks_are_used_instead_of_defaults() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), checks=[_AlwaysFailsCheck()])
    result = _assess(engine)
    assert result.validation_status == ValidationStatus.INVALID
    assert any(i.message == "custom failure" for i in result.errors)


def test_empty_checks_list_runs_no_checks() -> None:
    engine = RiskEngine(RiskEngineConfig(engine_version="v1"), checks=[])
    result = _assess(engine)
    assert result.errors == ()
    assert result.warnings == ()
