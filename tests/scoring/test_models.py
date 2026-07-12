from datetime import datetime, timezone

from btengine.scoring.models import (
    FeatureStatus,
    ScoreComponent,
    StrategyScore,
    StrategyScoreValidationIssue,
    ValidationStatus,
)

UTC = timezone.utc


def test_score_component_defaults_explanation_to_empty_string() -> None:
    component = ScoreComponent(
        provider_name="funding", provider_version="v1", value=None, weight=None, confidence=None
    )
    assert component.explanation == ""


def test_score_component_accepts_explicit_explanation() -> None:
    component = ScoreComponent(
        provider_name="funding", provider_version="v1", value=0.5, weight=1.0, confidence=1.0,
        explanation="computed from funding trend",
    )
    assert component.explanation == "computed from funding trend"


def test_strategy_score_defaults() -> None:
    score = StrategyScore(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), score_version="v1",
        funding_score=None, oi_score=None, premium_discount_score=None, liquidity_score=None,
        total_score=None, confidence=None,
    )
    assert score.feature_status == {}
    assert score.validation_status == ValidationStatus.VALID
    assert score.validation_issues == ()


def test_strategy_score_carries_components_and_issues() -> None:
    component = ScoreComponent(
        provider_name="funding", provider_version="v1", value=0.5, weight=1.0, confidence=1.0
    )
    issue = StrategyScoreValidationIssue("WARNING", "example issue", "funding")
    score = StrategyScore(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), score_version="v1",
        funding_score=component, oi_score=None, premium_discount_score=None, liquidity_score=None,
        total_score=0.5, confidence=1.0,
        feature_status={"funding": FeatureStatus.AVAILABLE},
        validation_status=ValidationStatus.WARNING,
        validation_issues=(issue,),
    )
    assert score.funding_score is component
    assert score.validation_issues == (issue,)
    assert score.feature_status["funding"] == FeatureStatus.AVAILABLE


def test_validation_issue_defaults_provider_name_to_none() -> None:
    issue = StrategyScoreValidationIssue("ERROR", "something failed")
    assert issue.provider_name is None
