import math

from btengine.scoring.config import ScoringEngineConfig
from btengine.scoring.models import ScoreComponent
from btengine.scoring.validation import StrategyScoreValidator


def _component(
    value: float | None = 0.5, confidence: float | None = 1.0, version: str = "v1",
    provider_name: str = "funding",
) -> ScoreComponent:
    return ScoreComponent(
        provider_name=provider_name, provider_version=version, value=value, weight=1.0, confidence=confidence
    )


def test_well_formed_components_have_no_issues() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component()})
    assert issues == []


def test_empty_components_have_no_issues_when_nothing_required() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    assert StrategyScoreValidator(config).validate({}) == []


# --- missing modules -----------------------------------------------------------


def test_missing_required_provider_is_flagged_as_error() -> None:
    config = ScoringEngineConfig(engine_version="v1", required_providers=("funding",))
    issues = StrategyScoreValidator(config).validate({"funding": None})
    assert any(i.severity == "ERROR" and "funding" in i.message and "missing" in i.message for i in issues)


def test_required_provider_present_is_not_flagged() -> None:
    config = ScoringEngineConfig(engine_version="v1", required_providers=("funding",))
    issues = StrategyScoreValidator(config).validate({"funding": _component(version="v1")})
    assert not any("missing" in i.message for i in issues)


def test_missing_modules_not_checked_when_nothing_required() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": None})
    assert not any("missing" in i.message for i in issues)


# --- missing feature inputs (zero confidence) -----------------------------------


def test_zero_confidence_component_is_flagged_as_warning() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(confidence=0.0)})
    assert any(i.severity == "WARNING" and "zero confidence" in i.message for i in issues)


def test_nonzero_confidence_component_is_not_flagged() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(confidence=0.5)})
    assert not any("zero confidence" in i.message for i in issues)


def test_none_confidence_component_is_not_flagged() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(confidence=None)})
    assert not any("zero confidence" in i.message for i in issues)


# --- invalid scores --------------------------------------------------------------


def test_nan_score_is_flagged_as_error() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(value=float("nan"))})
    assert any(i.severity == "ERROR" and "NaN" in i.message for i in issues)


def test_infinite_score_is_flagged_as_error() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(value=float("inf"))})
    assert any(i.severity == "ERROR" and "infinite" in i.message for i in issues)


def test_score_out_of_range_is_flagged_as_error() -> None:
    config = ScoringEngineConfig(engine_version="v1", score_min=0.0, score_max=1.0)
    issues = StrategyScoreValidator(config).validate({"funding": _component(value=1.5)})
    assert any(i.severity == "ERROR" and "outside" in i.message for i in issues)


def test_score_at_boundary_is_valid() -> None:
    config = ScoringEngineConfig(engine_version="v1", score_min=0.0, score_max=1.0)
    issues = StrategyScoreValidator(config).validate({"funding": _component(value=1.0)})
    assert not any("outside" in i.message for i in issues)


def test_none_value_is_not_flagged_as_invalid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(value=None)})
    assert not any("NaN" in i.message or "outside" in i.message for i in issues)


def test_none_component_is_not_flagged_as_invalid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": None})
    assert issues == []


# --- version mismatch ------------------------------------------------------------


def test_mismatched_provider_version_is_flagged_as_warning() -> None:
    config = ScoringEngineConfig(engine_version="v2")
    issues = StrategyScoreValidator(config).validate({"funding": _component(version="v1")})
    assert any(i.severity == "WARNING" and "version" in i.message for i in issues)


def test_matching_provider_version_is_not_flagged() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    issues = StrategyScoreValidator(config).validate({"funding": _component(version="v1")})
    assert not any("version" in i.message for i in issues)


def test_default_config_is_used_when_none_given() -> None:
    validator = StrategyScoreValidator()
    issues = validator.validate({"funding": _component(version="unversioned")})
    assert issues == []
