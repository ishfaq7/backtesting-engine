from pathlib import Path

import pytest

from btengine.scoring.config import (
    ConfidenceAggregationMethod,
    ScoreWeights,
    ScorePriorities,
    ScoringEngineConfig,
    load_scoring_engine_config,
    order_providers_by_priority,
    weights_from_scoring_model_config,
)
from btengine.scoring.errors import ScoringConfigError
from btengine.strategy.scoring.config import ScoringFactorConfig, ScoringModelConfig


# --- ScoreWeights ------------------------------------------------------------


def test_score_weights_default_to_none() -> None:
    weights = ScoreWeights()
    assert weights.funding is None
    assert weights.get("funding") is None


def test_score_weights_reject_negative_values() -> None:
    with pytest.raises(ValueError, match="funding"):
        ScoreWeights(funding=-1.0)


def test_score_weights_get_returns_configured_value() -> None:
    weights = ScoreWeights(funding=0.5)
    assert weights.get("funding") == 0.5
    assert weights.get("liquidity") is None


def test_score_weights_get_returns_none_for_unknown_name() -> None:
    assert ScoreWeights().get("unknown") is None


# --- ScorePriorities / order_providers_by_priority ----------------------------


def test_order_providers_by_priority_all_unset_breaks_ties_alphabetically() -> None:
    assert order_providers_by_priority(ScorePriorities()) == [
        "funding", "liquidity", "open_interest", "premium_discount",
    ]


def test_order_providers_by_priority_orders_ascending() -> None:
    priorities = ScorePriorities(funding=2, liquidity=1)
    assert order_providers_by_priority(priorities) == [
        "liquidity", "funding", "open_interest", "premium_discount",
    ]


def test_order_providers_by_priority_unset_sorts_last() -> None:
    priorities = ScorePriorities(liquidity=1)
    result = order_providers_by_priority(priorities)
    assert result[0] == "liquidity"
    assert set(result[1:]) == {"funding", "open_interest", "premium_discount"}


# --- ScoringEngineConfig -------------------------------------------------------


def test_engine_version_is_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="engine_version"):
        ScoringEngineConfig(engine_version="")
    with pytest.raises(ValueError, match="engine_version"):
        ScoringEngineConfig(engine_version="   ")


def test_defaults_are_valid() -> None:
    config = ScoringEngineConfig(engine_version="v1")
    assert config.weights == ScoreWeights()
    assert config.priorities == ScorePriorities()
    assert config.required_providers is None
    assert config.score_min == 0.0
    assert config.score_max == 1.0
    assert config.confidence_aggregation == ConfidenceAggregationMethod.MIN


def test_score_min_must_be_less_than_score_max() -> None:
    with pytest.raises(ValueError, match="score_min"):
        ScoringEngineConfig(engine_version="v1", score_min=1.0, score_max=1.0)


def test_required_providers_must_be_known_names() -> None:
    with pytest.raises(ValueError, match="unknown"):
        ScoringEngineConfig(engine_version="v1", required_providers=("not_a_provider",))


def test_required_providers_accepts_known_names() -> None:
    config = ScoringEngineConfig(engine_version="v1", required_providers=("funding", "liquidity"))
    assert config.required_providers == ("funding", "liquidity")


# --- weights_from_scoring_model_config ------------------------------------------


def test_weights_from_scoring_model_config_maps_known_source_rule_sets() -> None:
    model_config = ScoringModelConfig(
        version="0.1.0",
        factors=[
            ScoringFactorConfig(name="f1", source_rule_set="funding_rate", weight=0.4),
            ScoringFactorConfig(name="f2", source_rule_set="liquidity", weight=0.6),
        ],
    )
    weights = weights_from_scoring_model_config(model_config)
    assert weights.funding == 0.4
    assert weights.liquidity == 0.6
    assert weights.open_interest is None


def test_weights_from_scoring_model_config_ignores_unknown_source_rule_sets() -> None:
    model_config = ScoringModelConfig(
        version="0.1.0",
        factors=[ScoringFactorConfig(name="f1", source_rule_set="atr", weight=0.4)],
    )
    weights = weights_from_scoring_model_config(model_config)
    assert weights == ScoreWeights()


def test_weights_from_scoring_model_config_ignores_disabled_factors() -> None:
    model_config = ScoringModelConfig(
        version="0.1.0",
        factors=[
            ScoringFactorConfig(name="f1", source_rule_set="funding_rate", weight=0.4, enabled=False),
        ],
    )
    weights = weights_from_scoring_model_config(model_config)
    assert weights.funding is None


# --- load_scoring_engine_config --------------------------------------------------


def test_load_scoring_engine_config_reads_full_yaml(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text(
        "engine_version: v1\n"
        "weights:\n"
        "  funding: 0.4\n"
        "  liquidity: 0.6\n"
        "priorities:\n"
        "  funding: 1\n"
        "required_providers: [funding]\n"
        "score_min: 0.0\n"
        "score_max: 100.0\n"
        "confidence_aggregation: MEAN\n"
    )
    config = load_scoring_engine_config(path)
    assert config.engine_version == "v1"
    assert config.weights.funding == 0.4
    assert config.weights.liquidity == 0.6
    assert config.priorities.funding == 1
    assert config.required_providers == ("funding",)
    assert config.score_max == 100.0
    assert config.confidence_aggregation == ConfidenceAggregationMethod.MEAN


def test_load_scoring_engine_config_defaults_missing_sections(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("engine_version: v1\n")
    config = load_scoring_engine_config(path)
    assert config.weights == ScoreWeights()
    assert config.required_providers is None


def test_load_scoring_engine_config_requires_engine_version(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("weights:\n  funding: 0.5\n")
    with pytest.raises(ScoringConfigError, match="engine_version"):
        load_scoring_engine_config(path)


def test_load_scoring_engine_config_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ScoringConfigError):
        load_scoring_engine_config(tmp_path / "does_not_exist.yaml")


def test_load_scoring_engine_config_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("engine_version: [unclosed\n")
    with pytest.raises(ScoringConfigError, match="Invalid YAML"):
        load_scoring_engine_config(path)


def test_load_scoring_engine_config_raises_when_top_level_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(ScoringConfigError, match="mapping"):
        load_scoring_engine_config(path)


def test_load_scoring_engine_config_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("")
    with pytest.raises(ScoringConfigError, match="engine_version"):
        load_scoring_engine_config(path)


def test_load_scoring_engine_config_raises_on_invalid_field_value(tmp_path: Path) -> None:
    path = tmp_path / "scoring_engine.yaml"
    path.write_text("engine_version: v1\nscore_min: 1.0\nscore_max: 0.0\n")
    with pytest.raises(ScoringConfigError, match="invalid scoring engine config"):
        load_scoring_engine_config(path)
