from datetime import datetime, timezone

from btengine.decision.models import (
    DecisionContext,
    DecisionOutcome,
    DecisionStatus,
    DecisionValidationIssue,
)
from btengine.scoring.models import ValidationStatus

UTC = timezone.utc


def test_decision_validation_issue_defaults_provider_name_to_none() -> None:
    issue = DecisionValidationIssue("ERROR", "structural", "something failed")
    assert issue.provider_name is None


def test_decision_outcome_defaults_metadata_to_empty_dict() -> None:
    outcome = DecisionOutcome(
        provider_name="rule_based", provider_version="v1", status=DecisionStatus.PENDING, reason="not implemented"
    )
    assert outcome.metadata == {}


def test_decision_context_defaults() -> None:
    context = DecisionContext(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), strategy_version="v1",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), decision_status=DecisionStatus.PENDING,
        decision_reason="awaiting proprietary decision logic", validation_status=ValidationStatus.VALID,
        execution_ready=False,
    )
    assert context.provider_outcomes == ()
    assert context.validation_errors == ()
    assert context.validation_warnings == ()
    assert context.metadata == {}


def test_decision_status_values_contain_no_trading_vocabulary() -> None:
    values = {status.value for status in DecisionStatus}
    for forbidden in ("BUY", "SELL", "LONG", "SHORT", "ENTER", "EXIT"):
        assert forbidden not in values
    assert values == {"NOT_READY", "PENDING", "EVALUATED"}
