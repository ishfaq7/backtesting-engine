from pathlib import Path

import pytest

from btengine.risk.config import RiskEngineConfig, RiskProfile, load_risk_engine_config
from btengine.risk.errors import RiskEngineConfigError


# --- RiskProfile ------------------------------------------------------------------


def test_profile_defaults_every_limit_to_none() -> None:
    profile = RiskProfile(name="default")
    assert profile.max_leverage is None
    assert profile.max_risk_per_trade_pct is None
    assert profile.max_daily_drawdown_pct is None
    assert profile.max_total_drawdown_pct is None
    assert profile.max_exposure_pct is None
    assert profile.max_capital_allocation_pct is None
    assert profile.max_margin_utilization_pct is None
    assert profile.max_portfolio_risk_pct is None


def test_profile_name_must_not_be_empty() -> None:
    with pytest.raises(ValueError, match="name"):
        RiskProfile(name="  ")


def test_profile_limits_must_be_positive_when_set() -> None:
    with pytest.raises(ValueError, match="max_leverage"):
        RiskProfile(name="p", max_leverage=0)
    with pytest.raises(ValueError, match="max_exposure_pct"):
        RiskProfile(name="p", max_exposure_pct=-0.5)


def test_profile_accepts_valid_limits() -> None:
    profile = RiskProfile(name="p", max_leverage=5.0, max_risk_per_trade_pct=0.02)
    assert profile.max_leverage == 5.0


# --- RiskEngineConfig ---------------------------------------------------------------


def test_engine_version_is_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="engine_version"):
        RiskEngineConfig(engine_version="")


def test_defaults_are_valid() -> None:
    config = RiskEngineConfig(engine_version="v1")
    assert config.profiles == {}
    assert config.active_profile is None
    assert config.expected_strategy_version is None
    assert config.resolved_profile is None


def test_active_profile_must_be_registered() -> None:
    with pytest.raises(ValueError, match="active_profile"):
        RiskEngineConfig(engine_version="v1", active_profile="missing")


def test_profile_key_must_match_profile_name() -> None:
    with pytest.raises(ValueError, match="mismatched name"):
        RiskEngineConfig(
            engine_version="v1", profiles={"a": RiskProfile(name="b")}
        )


def test_resolved_profile_returns_active_profile() -> None:
    profile = RiskProfile(name="conservative", max_leverage=3.0)
    config = RiskEngineConfig(
        engine_version="v1", profiles={"conservative": profile}, active_profile="conservative"
    )
    assert config.resolved_profile is profile


# --- load_risk_engine_config ------------------------------------------------------------


def test_load_reads_full_yaml(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text(
        "engine_version: v1\n"
        "expected_strategy_version: v1\n"
        "active_profile: conservative\n"
        "profiles:\n"
        "  conservative:\n"
        "    max_leverage: 3.0\n"
        "    max_risk_per_trade_pct: 0.01\n"
        "  aggressive:\n"
        "    max_leverage: 10.0\n"
    )
    config = load_risk_engine_config(path)
    assert config.engine_version == "v1"
    assert config.active_profile == "conservative"
    assert config.resolved_profile.max_leverage == 3.0
    assert config.profiles["aggressive"].max_leverage == 10.0
    assert config.profiles["aggressive"].max_risk_per_trade_pct is None


def test_load_defaults_missing_sections(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("engine_version: v1\n")
    config = load_risk_engine_config(path)
    assert config.profiles == {}
    assert config.active_profile is None


def test_load_handles_profile_with_empty_body(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("engine_version: v1\nprofiles:\n  default:\n")
    config = load_risk_engine_config(path)
    assert config.profiles["default"].max_leverage is None


def test_load_requires_engine_version(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("active_profile: null\n")
    with pytest.raises(RiskEngineConfigError, match="engine_version"):
        load_risk_engine_config(path)


def test_load_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(RiskEngineConfigError):
        load_risk_engine_config(tmp_path / "does_not_exist.yaml")


def test_load_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("engine_version: [unclosed\n")
    with pytest.raises(RiskEngineConfigError, match="Invalid YAML"):
        load_risk_engine_config(path)


def test_load_raises_when_top_level_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("- a\n- list\n")
    with pytest.raises(RiskEngineConfigError, match="mapping"):
        load_risk_engine_config(path)


def test_load_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("")
    with pytest.raises(RiskEngineConfigError, match="engine_version"):
        load_risk_engine_config(path)


def test_load_raises_on_invalid_profile_value(tmp_path: Path) -> None:
    path = tmp_path / "risk_engine.yaml"
    path.write_text("engine_version: v1\nprofiles:\n  p:\n    max_leverage: -1\n")
    with pytest.raises(RiskEngineConfigError, match="invalid risk engine config"):
        load_risk_engine_config(path)
