from pathlib import Path

import pytest

from btengine.decision.config import (
    DecisionEngineConfig,
    load_decision_engine_config,
    order_provider_names_by_priority,
)
from btengine.decision.errors import DecisionEngineConfigError


def test_defaults_are_valid() -> None:
    config = DecisionEngineConfig(engine_version="v1")
    assert config.expected_strategy_version is None
    assert config.required_providers is None
    assert config.provider_priorities == {}
    assert config.require_validation_passed is True
    assert config.history_window == 20


def test_engine_version_is_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="engine_version"):
        DecisionEngineConfig(engine_version="")
    with pytest.raises(ValueError, match="engine_version"):
        DecisionEngineConfig(engine_version="   ")


def test_history_window_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="history_window"):
        DecisionEngineConfig(engine_version="v1", history_window=0)


def test_valid_custom_config() -> None:
    config = DecisionEngineConfig(
        engine_version="v1", expected_strategy_version="v1", required_providers=("rule_based",),
        provider_priorities={"rule_based": 1}, require_validation_passed=False, history_window=5,
    )
    assert config.required_providers == ("rule_based",)
    assert config.require_validation_passed is False


# --- order_provider_names_by_priority ------------------------------------------


def test_order_providers_all_unset_breaks_ties_alphabetically() -> None:
    assert order_provider_names_by_priority(["b", "a", "c"], {}) == ["a", "b", "c"]


def test_order_providers_orders_ascending() -> None:
    assert order_provider_names_by_priority(["a", "b"], {"a": 2, "b": 1}) == ["b", "a"]


def test_order_providers_unset_sorts_last() -> None:
    result = order_provider_names_by_priority(["a", "b", "c"], {"b": 1})
    assert result[0] == "b"
    assert set(result[1:]) == {"a", "c"}


def test_order_providers_handles_empty_list() -> None:
    assert order_provider_names_by_priority([], {}) == []


# --- load_decision_engine_config -------------------------------------------------


def test_load_reads_full_yaml(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text(
        "engine_version: v1\n"
        "expected_strategy_version: v1\n"
        "required_providers: [rule_based]\n"
        "provider_priorities:\n"
        "  rule_based: 1\n"
        "require_validation_passed: false\n"
        "history_window: 5\n"
    )
    config = load_decision_engine_config(path)
    assert config.engine_version == "v1"
    assert config.required_providers == ("rule_based",)
    assert config.provider_priorities == {"rule_based": 1}
    assert config.require_validation_passed is False
    assert config.history_window == 5


def test_load_defaults_missing_sections(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("engine_version: v1\n")
    config = load_decision_engine_config(path)
    assert config.required_providers is None
    assert config.provider_priorities == {}
    assert config.require_validation_passed is True
    assert config.history_window == 20


def test_load_requires_engine_version(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("require_validation_passed: true\n")
    with pytest.raises(DecisionEngineConfigError, match="engine_version"):
        load_decision_engine_config(path)


def test_load_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DecisionEngineConfigError):
        load_decision_engine_config(tmp_path / "does_not_exist.yaml")


def test_load_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("engine_version: [unclosed\n")
    with pytest.raises(DecisionEngineConfigError, match="Invalid YAML"):
        load_decision_engine_config(path)


def test_load_raises_when_top_level_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(DecisionEngineConfigError, match="mapping"):
        load_decision_engine_config(path)


def test_load_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("")
    with pytest.raises(DecisionEngineConfigError, match="engine_version"):
        load_decision_engine_config(path)


def test_load_raises_on_invalid_field_value(tmp_path: Path) -> None:
    path = tmp_path / "decision_engine.yaml"
    path.write_text("engine_version: v1\nhistory_window: 0\n")
    with pytest.raises(DecisionEngineConfigError, match="invalid decision engine config"):
        load_decision_engine_config(path)
