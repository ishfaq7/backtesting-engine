from datetime import datetime, timezone

from btengine.signal_validation.models import (
    ConfidenceStatus,
    DataIntegrityStatus,
    FeatureCompleteness,
    ModuleHealthStatus,
    SignalValidationIssue,
    ValidatedStrategyState,
)
from tests.signal_validation.conftest import make_strategy_score

UTC = timezone.utc


def test_signal_validation_issue_defaults_provider_name_to_none() -> None:
    issue = SignalValidationIssue("ERROR", "structural", "something failed")
    assert issue.provider_name is None


def test_feature_completeness_holds_given_fields() -> None:
    completeness = FeatureCompleteness(
        available_providers=("funding",), missing_providers=("liquidity",),
        completeness_ratio=0.5, is_sufficient=None,
    )
    assert completeness.available_providers == ("funding",)
    assert completeness.is_sufficient is None


def test_validated_strategy_state_defaults() -> None:
    score = make_strategy_score()
    state = ValidatedStrategyState(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), strategy_version="v1",
        score=score, validation_passed=True, validation_errors=(), validation_warnings=(),
        confidence_status=ConfidenceStatus.VALID,
        feature_completeness=FeatureCompleteness((), (), 0.0, None),
    )
    assert state.module_health == {}
    assert state.data_integrity == DataIntegrityStatus.VALID


def test_validated_strategy_state_carries_score_unmodified() -> None:
    score = make_strategy_score()
    state = ValidatedStrategyState(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), strategy_version="v1",
        score=score, validation_passed=True, validation_errors=(), validation_warnings=(),
        confidence_status=ConfidenceStatus.VALID,
        feature_completeness=FeatureCompleteness((), (), 0.0, None),
        module_health={"funding": ModuleHealthStatus.HEALTHY},
    )
    assert state.score is score
