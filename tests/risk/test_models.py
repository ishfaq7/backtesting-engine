from datetime import datetime, timezone

from btengine.risk.models import (
    ExposureStatus,
    RiskAssessment,
    RiskModuleResult,
    RiskValidationIssue,
)
from btengine.scoring.models import ValidationStatus

UTC = timezone.utc


def test_risk_validation_issue_defaults_module_name_to_none() -> None:
    issue = RiskValidationIssue("ERROR", "structural", "bad input")
    assert issue.module_name is None


def test_risk_module_result_supports_tristate_approved() -> None:
    result = RiskModuleResult(
        module_name="position_sizing", module_version="v1", approved=None, value=None,
        reason="not implemented",
    )
    assert result.approved is None
    assert result.metadata == {}


def test_risk_assessment_defaults() -> None:
    assessment = RiskAssessment(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), strategy_version="v1",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), risk_approved=False, position_size=None,
        leverage_allowed=None, max_risk_allowed=None, exposure_status=ExposureStatus.UNKNOWN,
        portfolio_risk=None, validation_status=ValidationStatus.VALID,
    )
    assert assessment.module_results == ()
    assert assessment.errors == ()
    assert assessment.warnings == ()
    assert assessment.metadata == {}


def test_exposure_status_values() -> None:
    assert {status.value for status in ExposureStatus} == {"WITHIN_LIMITS", "EXCEEDED", "UNKNOWN"}
