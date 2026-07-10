import pytest
from pydantic import ValidationError

from btengine.strategy.scoring.config import ScoringFactorConfig, ScoringModelConfig


def test_version_is_required() -> None:
    with pytest.raises(ValidationError):
        ScoringModelConfig()  # type: ignore[call-arg]


def test_minimal_valid_config() -> None:
    config = ScoringModelConfig(version="0.1.0")
    assert config.enabled is False
    assert config.factors == []
    assert config.entry_threshold is None
    assert config.ai_scoring_enabled is False


def test_factor_defaults() -> None:
    factor = ScoringFactorConfig(name="f1")
    assert factor.source_rule_set == ""
    assert factor.weight is None
    assert factor.enabled is True


def test_duplicate_factor_names_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoringModelConfig(
            version="0.1.0",
            factors=[ScoringFactorConfig(name="f1"), ScoringFactorConfig(name="f1")],
        )


def test_distinct_factor_names_accepted() -> None:
    config = ScoringModelConfig(
        version="0.1.0",
        factors=[ScoringFactorConfig(name="f1"), ScoringFactorConfig(name="f2")],
    )
    assert len(config.factors) == 2


def test_ai_scoring_enabled_requires_model_name() -> None:
    with pytest.raises(ValidationError):
        ScoringModelConfig(version="0.1.0", ai_scoring_enabled=True)


def test_ai_scoring_enabled_with_model_name_is_valid() -> None:
    config = ScoringModelConfig(version="0.1.0", ai_scoring_enabled=True, ai_model_name="my-model-v1")
    assert config.ai_model_name == "my-model-v1"


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ScoringModelConfig(version="0.1.0", unexpected_field=1)  # type: ignore[call-arg]
