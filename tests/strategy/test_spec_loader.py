from pathlib import Path

import pytest

from btengine.strategy.spec_errors import SpecLoadError
from btengine.strategy.spec_loader import load_strategy_spec


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_loads_minimal_spec(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: my-strategy\nversion: 0.1.0\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")

    spec = load_strategy_spec(tmp_path)
    assert spec.name == "my-strategy"
    assert spec.version == "0.1.0"
    assert spec.scoring.version == "0.1.0"
    assert spec.funding_rate_rules.enabled is False


def test_missing_scoring_file_fails_validation(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: x\nversion: 0.1.0\n")
    with pytest.raises(SpecLoadError):
        load_strategy_spec(tmp_path)


def test_missing_strategy_file_fails_validation(tmp_path: Path) -> None:
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    with pytest.raises(SpecLoadError):
        load_strategy_spec(tmp_path)  # name is required, absent here


def test_loads_a_rule_category_file(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: x\nversion: 0.1.0\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    _write(
        tmp_path / "rules" / "funding_rate.yaml",
        "enabled: true\n"
        "conditions:\n"
        "  - name: c1\n"
        "    feature: funding_rate\n"
        "    operator: GT\n"
        "    value: 0.0001\n",
    )

    spec = load_strategy_spec(tmp_path)
    assert spec.funding_rate_rules.enabled is True
    assert len(spec.funding_rate_rules.conditions) == 1
    assert spec.funding_rate_rules.conditions[0].feature == "funding_rate"


def test_missing_rule_files_default_to_empty_and_disabled(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: x\nversion: 0.1.0\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    spec = load_strategy_spec(tmp_path)
    assert spec.liquidity_rules.enabled is False
    assert spec.risk_management_rules.enabled is False


def test_unreadable_spec_file_raises_spec_load_error(tmp_path: Path) -> None:
    # A directory where a file is expected fails read_text() with an OSError.
    (tmp_path / "strategy.yaml").mkdir()
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    with pytest.raises(SpecLoadError):
        load_strategy_spec(tmp_path)


def test_invalid_yaml_raises_spec_load_error(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: x\nversion: 0.1.0\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    _write(tmp_path / "rules" / "funding_rate.yaml", "enabled: [this is not valid: yaml: at all")
    with pytest.raises(SpecLoadError):
        load_strategy_spec(tmp_path)


def test_non_mapping_yaml_raises_spec_load_error(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "- just\n- a\n- list\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    with pytest.raises(SpecLoadError):
        load_strategy_spec(tmp_path)


def test_empty_yaml_file_is_treated_as_empty_mapping(tmp_path: Path) -> None:
    _write(tmp_path / "strategy.yaml", "name: x\nversion: 0.1.0\n")
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    _write(tmp_path / "rules" / "liquidity.yaml", "")
    spec = load_strategy_spec(tmp_path)
    assert spec.liquidity_rules.enabled is False


def test_known_assumptions_and_todo_load_from_top_level_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "strategy.yaml",
        "name: x\nversion: 0.1.0\nknown_assumptions:\n  - assumption one\ntodo:\n  - todo one\n",
    )
    _write(tmp_path / "scoring.yaml", "version: 0.1.0\n")
    spec = load_strategy_spec(tmp_path)
    assert spec.known_assumptions == ["assumption one"]
    assert spec.todo == ["todo one"]
