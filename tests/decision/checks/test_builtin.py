from datetime import datetime, timezone

from btengine.decision.checks.builtin import (
    InvalidAnalysisObjectsCheck,
    InvalidScoreObjectCheck,
    MissingInputsCheck,
    StrategyVersionMismatchCheck,
    UnsupportedDecisionProvidersCheck,
    default_checks,
)
from btengine.decision.config import DecisionEngineConfig
from btengine.decision.context import DecisionRequest
from btengine.scoring.models import StrategyScore
from tests.decision.conftest import (
    make_funding_analysis,
    make_strategy_score,
    make_validated_strategy_state,
)

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def _request(
    config: DecisionEngineConfig | None = None,
    *,
    symbol: str = "BTCUSDT",
    validated_state=None,
    funding=None,
    open_interest=None,
    premium_discount=None,
    liquidity=None,
    provider_names: tuple[str, ...] = (),
) -> DecisionRequest:
    return DecisionRequest(
        symbol=symbol, reference_time=NOW, validated_state=validated_state or make_validated_strategy_state(),
        funding=funding, open_interest=open_interest, premium_discount=premium_discount, liquidity=liquidity,
        config=config or DecisionEngineConfig(engine_version="v1"), provider_names=provider_names,
    )


def test_default_checks_returns_five_checks() -> None:
    assert len(default_checks()) == 5


def test_default_checks_have_unique_stable_names() -> None:
    names = [check.check_name for check in default_checks()]
    assert names == [
        "missing_inputs", "invalid_score_object", "invalid_analysis_objects",
        "strategy_version_mismatch", "unsupported_decision_providers",
    ]
    assert len(set(names)) == len(names)


# --- MissingInputsCheck ------------------------------------------------------------


def test_missing_inputs_flags_every_absent_analysis() -> None:
    issues = MissingInputsCheck().run(_request())
    names = {i.provider_name for i in issues}
    assert names == {"funding", "open_interest", "premium_discount", "liquidity"}
    assert all(i.severity == "WARNING" for i in issues)


def test_missing_inputs_does_not_flag_supplied_analyses() -> None:
    issues = MissingInputsCheck().run(_request(funding=make_funding_analysis()))
    assert "funding" not in {i.provider_name for i in issues}


# --- InvalidScoreObjectCheck --------------------------------------------------------


def test_invalid_score_object_flags_empty_symbol() -> None:
    score = make_strategy_score(symbol="")
    request = _request(validated_state=make_validated_strategy_state(score=score))
    issues = InvalidScoreObjectCheck().run(request)
    assert any("empty symbol" in i.message for i in issues)


def test_invalid_score_object_flags_naive_timestamp() -> None:
    good_score = make_strategy_score()
    naive_score = StrategyScore(
        symbol=good_score.symbol, as_of=datetime(2024, 1, 1), score_version=good_score.score_version,
        funding_score=None, oi_score=None, premium_discount_score=None, liquidity_score=None,
        total_score=None, confidence=good_score.confidence, feature_status=good_score.feature_status,
    )
    state = make_validated_strategy_state(score=naive_score)
    issues = InvalidScoreObjectCheck().run(_request(validated_state=state))
    assert any("timezone-aware" in i.message for i in issues)


def test_invalid_score_object_flags_empty_score_version() -> None:
    score = make_strategy_score(score_version="")
    state = make_validated_strategy_state(score=score, strategy_version="")
    issues = InvalidScoreObjectCheck().run(_request(validated_state=state))
    assert any("empty score_version" in i.message for i in issues)


def test_invalid_score_object_flags_invalid_confidence() -> None:
    score = make_strategy_score(confidence=float("nan"))
    state = make_validated_strategy_state(score=score)
    issues = InvalidScoreObjectCheck().run(_request(validated_state=state))
    assert any("invalid confidence" in i.message for i in issues)


def test_invalid_score_object_none_confidence_is_not_flagged() -> None:
    score = make_strategy_score(confidence=None)
    state = make_validated_strategy_state(score=score)
    issues = InvalidScoreObjectCheck().run(_request(validated_state=state))
    assert not any("confidence" in i.message for i in issues)


def test_invalid_score_object_no_issues_for_well_formed_score() -> None:
    assert InvalidScoreObjectCheck().run(_request()) == []


# --- InvalidAnalysisObjectsCheck --------------------------------------------------------


def test_invalid_analysis_objects_flags_empty_symbol() -> None:
    funding = make_funding_analysis(symbol="")
    issues = InvalidAnalysisObjectsCheck().run(_request(funding=funding))
    assert any("empty symbol" in i.message for i in issues)


def test_invalid_analysis_objects_flags_naive_timestamp() -> None:
    funding = make_funding_analysis()
    from dataclasses import replace

    naive_funding = replace(funding, as_of=datetime(2024, 1, 1))
    issues = InvalidAnalysisObjectsCheck().run(_request(funding=naive_funding))
    assert any("timezone-aware" in i.message for i in issues)


def test_invalid_analysis_objects_flags_invalid_confidence() -> None:
    funding = make_funding_analysis(confidence_level=2.0)
    issues = InvalidAnalysisObjectsCheck().run(_request(funding=funding))
    assert any("invalid confidence_level" in i.message for i in issues)


def test_invalid_analysis_objects_no_issues_when_absent() -> None:
    assert InvalidAnalysisObjectsCheck().run(_request()) == []


def test_invalid_analysis_objects_no_issues_for_well_formed_analysis() -> None:
    issues = InvalidAnalysisObjectsCheck().run(_request(funding=make_funding_analysis()))
    assert issues == []


# --- StrategyVersionMismatchCheck --------------------------------------------------------


def test_strategy_version_mismatch_flags_unexpected_version() -> None:
    config = DecisionEngineConfig(engine_version="v1", expected_strategy_version="v2")
    state = make_validated_strategy_state(strategy_version="v1")
    issues = StrategyVersionMismatchCheck().run(_request(config, validated_state=state))
    assert any("does not match" in i.message for i in issues)


def test_strategy_version_mismatch_not_checked_without_expected_version() -> None:
    state = make_validated_strategy_state(strategy_version="v1")
    issues = StrategyVersionMismatchCheck().run(_request(validated_state=state))
    assert not any("does not match" in i.message for i in issues)


def test_strategy_version_mismatch_flags_internal_disagreement() -> None:
    score = make_strategy_score(score_version="v1")
    state = make_validated_strategy_state(score=score, strategy_version="v2")
    issues = StrategyVersionMismatchCheck().run(_request(validated_state=state))
    assert any("disagrees" in i.message for i in issues)


def test_strategy_version_mismatch_no_issue_when_consistent() -> None:
    assert StrategyVersionMismatchCheck().run(_request()) == []


# --- UnsupportedDecisionProvidersCheck --------------------------------------------------------


def test_unsupported_decision_providers_flags_missing_required_provider() -> None:
    config = DecisionEngineConfig(engine_version="v1", required_providers=("rule_based",))
    issues = UnsupportedDecisionProvidersCheck().run(_request(config, provider_names=()))
    assert any(i.severity == "ERROR" and "rule_based" in i.message for i in issues)


def test_unsupported_decision_providers_no_issue_when_registered() -> None:
    config = DecisionEngineConfig(engine_version="v1", required_providers=("rule_based",))
    issues = UnsupportedDecisionProvidersCheck().run(
        _request(config, provider_names=("rule_based",))
    )
    assert issues == []


def test_unsupported_decision_providers_no_issue_when_none_required() -> None:
    assert UnsupportedDecisionProvidersCheck().run(_request()) == []
