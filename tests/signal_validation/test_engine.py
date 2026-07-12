from datetime import datetime, timedelta, timezone

import pytest

from btengine.scoring.models import FeatureStatus
from btengine.signal_validation.checks.base import ValidationCheck
from btengine.signal_validation.config import SignalValidationConfig
from btengine.signal_validation.engine import SignalValidationEngine
from btengine.signal_validation.models import (
    ConfidenceStatus,
    DataIntegrityStatus,
    ModuleHealthStatus,
    SignalValidationIssue,
)
from tests.signal_validation.conftest import make_funding_analysis, make_strategy_score

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def test_validate_returns_score_unmodified() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score()
    state = engine.validate("BTCUSDT", NOW, score=score)
    assert state.score is score


def test_validate_uppercases_symbol() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("btcusdt", NOW, score=make_strategy_score())
    assert state.symbol == "BTCUSDT"


def test_validate_passes_with_no_issues() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score()
    state = engine.validate(
        "BTCUSDT", NOW, score=score, funding=make_funding_analysis(),
        open_interest=None, premium_discount=None, liquidity=None,
    )
    # missing analyses still produce WARNINGs, so validation_passed stays True
    assert state.validation_passed is True
    assert state.validation_errors == ()


def test_validate_fails_on_error_level_issue() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score(symbol="ETHUSDT")  # will conflict with requested "BTCUSDT"
    state = engine.validate("BTCUSDT", NOW, score=score)
    assert state.validation_passed is False
    assert len(state.validation_errors) >= 1


def test_strategy_version_matches_score_version() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score(score_version="v42")
    state = engine.validate("BTCUSDT", NOW, score=score)
    assert state.strategy_version == "v42"


# --- confidence status -------------------------------------------------------------


def test_confidence_status_unknown_when_none() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=None))
    assert state.confidence_status == ConfidenceStatus.UNKNOWN


def test_confidence_status_invalid_when_nan() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=float("nan")))
    assert state.confidence_status == ConfidenceStatus.INVALID


def test_confidence_status_invalid_when_out_of_range() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=1.5))
    assert state.confidence_status == ConfidenceStatus.INVALID


def test_confidence_status_low_when_below_threshold() -> None:
    config = SignalValidationConfig(engine_version="v1", min_confidence=0.5)
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=0.3))
    assert state.confidence_status == ConfidenceStatus.LOW


def test_confidence_status_valid_otherwise() -> None:
    config = SignalValidationConfig(engine_version="v1", min_confidence=0.5)
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=0.9))
    assert state.confidence_status == ConfidenceStatus.VALID


# --- feature completeness -----------------------------------------------------------


def test_feature_completeness_ratio_and_lists() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.AVAILABLE, "liquidity": FeatureStatus.MISSING,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score)
    completeness = state.feature_completeness
    assert completeness.available_providers == ("funding", "premium_discount")
    assert completeness.missing_providers == ("liquidity", "open_interest")
    assert completeness.completeness_ratio == pytest.approx(0.5)
    assert completeness.is_sufficient is None


def test_feature_completeness_is_sufficient_when_threshold_configured() -> None:
    config = SignalValidationConfig(engine_version="v1", min_completeness_ratio=0.5)
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score())  # 4/4 available
    assert state.feature_completeness.is_sufficient is True


def test_feature_completeness_is_insufficient_when_below_threshold() -> None:
    config = SignalValidationConfig(engine_version="v1", min_completeness_ratio=0.9)
    engine = SignalValidationEngine(config)
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score)
    assert state.feature_completeness.is_sufficient is False


def test_feature_completeness_handles_empty_feature_status() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(feature_status={}))
    assert state.feature_completeness.completeness_ratio == 0.0


# --- module health -------------------------------------------------------------------


def test_module_health_reflects_feature_status() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.NOT_IMPLEMENTED, "liquidity": FeatureStatus.INVALID,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score)
    assert state.module_health["funding"] == ModuleHealthStatus.HEALTHY
    assert state.module_health["open_interest"] == ModuleHealthStatus.MISSING
    assert state.module_health["premium_discount"] == ModuleHealthStatus.NOT_IMPLEMENTED
    assert state.module_health["liquidity"] == ModuleHealthStatus.INVALID


def test_module_health_stale_when_available_but_beyond_max_staleness() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    engine = SignalValidationEngine(config)
    old_funding = make_funding_analysis(as_of=NOW - timedelta(hours=2))
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score, funding=old_funding)
    assert state.module_health["funding"] == ModuleHealthStatus.STALE


def test_module_health_healthy_when_available_and_fresh() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    engine = SignalValidationEngine(config)
    fresh_funding = make_funding_analysis(as_of=NOW - timedelta(minutes=5))
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score, funding=fresh_funding)
    assert state.module_health["funding"] == ModuleHealthStatus.HEALTHY


def test_module_health_healthy_when_available_but_no_analysis_given() -> None:
    # AVAILABLE with no corresponding analysis object supplied (edge case)
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    engine = SignalValidationEngine(config)
    score = make_strategy_score(
        feature_status={
            "funding": FeatureStatus.AVAILABLE, "open_interest": FeatureStatus.MISSING,
            "premium_discount": FeatureStatus.MISSING, "liquidity": FeatureStatus.MISSING,
        }
    )
    state = engine.validate("BTCUSDT", NOW, score=score)  # funding analysis not supplied
    assert state.module_health["funding"] == ModuleHealthStatus.HEALTHY


# --- data integrity rollup -------------------------------------------------------------


def test_data_integrity_valid_with_no_issues() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score())
    assert state.data_integrity == DataIntegrityStatus.VALID


def test_data_integrity_stale_takes_priority() -> None:
    config = SignalValidationConfig(engine_version="v1", max_staleness=timedelta(hours=1))
    engine = SignalValidationEngine(config)
    old_funding = make_funding_analysis(as_of=NOW - timedelta(hours=2))
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(), funding=old_funding)
    assert state.data_integrity == DataIntegrityStatus.STALE


def test_data_integrity_inconsistent_on_symbol_mismatch() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    mismatched_funding = make_funding_analysis(symbol="ETHUSDT")
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(), funding=mismatched_funding)
    assert state.data_integrity == DataIntegrityStatus.INCONSISTENT


def test_data_integrity_invalid_for_other_errors() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(confidence=float("nan")))
    assert state.data_integrity == DataIntegrityStatus.INVALID


# --- duplicate signal detection -----------------------------------------------------------


def test_duplicate_signal_flagged_on_second_call() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    score = make_strategy_score()
    first = engine.validate("BTCUSDT", NOW, score=score)
    second = engine.validate("BTCUSDT", NOW, score=score)
    assert not any("duplicate" in i.message for i in first.validation_warnings)
    assert any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_signal_not_flagged_for_different_as_of() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    second = engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW + timedelta(hours=1)))
    assert not any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_signal_not_flagged_for_different_symbol() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(symbol="BTCUSDT"))
    second = engine.validate("ETHUSDT", NOW, score=make_strategy_score(symbol="ETHUSDT"))
    assert not any("duplicate" in i.message for i in second.validation_warnings)


def test_duplicate_signal_case_insensitive_symbol() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("btcusdt", NOW, score=make_strategy_score())
    second = engine.validate("BTCUSDT", NOW, score=make_strategy_score())
    assert any("duplicate" in i.message for i in second.validation_warnings)


# --- historical consistency (monotonic as_of) --------------------------------------------


def test_historical_consistency_no_issue_on_first_call() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    assert not any(i.category == "sequencing" for i in state.validation_errors)


def test_historical_consistency_no_issue_when_strictly_increasing() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    later = engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW + timedelta(hours=1)))
    assert not any(i.category == "sequencing" for i in later.validation_errors)


def test_historical_consistency_flags_out_of_order_replay() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    earlier = engine.validate(
        "BTCUSDT", NOW, score=make_strategy_score(as_of=NOW - timedelta(hours=1))
    )
    assert any(i.category == "sequencing" for i in earlier.validation_errors)
    assert earlier.validation_passed is False


def test_historical_consistency_flags_equal_as_of_as_out_of_order() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    repeat = engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    assert any(i.category == "sequencing" for i in repeat.validation_errors)


def test_historical_consistency_is_scoped_per_symbol() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(symbol="BTCUSDT", as_of=NOW))
    other_symbol = engine.validate(
        "ETHUSDT", NOW, score=make_strategy_score(symbol="ETHUSDT", as_of=NOW - timedelta(days=1))
    )
    assert not any(i.category == "sequencing" for i in other_symbol.validation_errors)


def test_historical_consistency_respects_history_window(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SignalValidationConfig(engine_version="v1", history_window=2)
    engine = SignalValidationEngine(config)
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW))
    engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW + timedelta(hours=1)))
    latest = engine.validate("BTCUSDT", NOW, score=make_strategy_score(as_of=NOW + timedelta(hours=2)))
    assert latest.validation_passed is True


# --- dependency injection: custom checks -----------------------------------------------------


class _AlwaysFailsCheck(ValidationCheck):
    @property
    def check_name(self) -> str:
        return "always_fails"

    def run(self, context) -> list[SignalValidationIssue]:
        return [SignalValidationIssue("ERROR", "custom", "custom failure")]


def test_custom_checks_are_used_instead_of_defaults() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config, checks=[_AlwaysFailsCheck()])
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score())
    assert state.validation_passed is False
    assert any(i.message == "custom failure" for i in state.validation_errors)


def test_empty_checks_list_runs_no_stateless_checks() -> None:
    config = SignalValidationConfig(engine_version="v1")
    engine = SignalValidationEngine(config, checks=[])
    state = engine.validate("BTCUSDT", NOW, score=make_strategy_score())
    assert state.validation_errors == ()
    assert state.validation_warnings == ()
