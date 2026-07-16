from datetime import datetime, timezone
from pathlib import Path

import pytest

from btengine.no_trade.config import NoTradeEngineConfig, load_no_trade_engine_config
from btengine.no_trade.errors import NoTradeEngineConfigError
from btengine.no_trade.models import (
    FilterResult,
    FilterVerdict,
    NoTradeAssessment,
    NoTradeValidationIssue,
)
from btengine.scoring.models import ValidationStatus

UTC = timezone.utc


# --- models ---------------------------------------------------------------------


def test_filter_verdict_is_tristate_with_no_trading_vocabulary() -> None:
    assert {verdict.value for verdict in FilterVerdict} == {"ALLOW", "BLOCK", "CANNOT_EVALUATE"}


def test_filter_result_defaults_metadata_to_empty_dict() -> None:
    result = FilterResult(
        filter_name="time_filter", filter_version="v1", verdict=FilterVerdict.CANNOT_EVALUATE,
        reason="not implemented",
    )
    assert result.metadata == {}


def test_no_trade_validation_issue_defaults_filter_name_to_none() -> None:
    issue = NoTradeValidationIssue("ERROR", "structural", "bad input")
    assert issue.filter_name is None


def test_no_trade_assessment_defaults() -> None:
    assessment = NoTradeAssessment(
        symbol="BTCUSDT", as_of=datetime(2024, 1, 1, tzinfo=UTC), strategy_version="v1",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC), trading_allowed=False,
        blocked_reasons=("no filters",), warning_messages=(), active_filters=(),
        validation_status=ValidationStatus.VALID,
    )
    assert assessment.filter_results == ()
    assert assessment.errors == ()
    assert assessment.metadata == {}


# --- config ----------------------------------------------------------------------


def test_config_defaults_are_valid() -> None:
    config = NoTradeEngineConfig(engine_version="v1")
    assert config.enabled_filters is None
    assert config.expected_strategy_version is None
    assert config.filter_parameters == {}


def test_engine_version_is_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="engine_version"):
        NoTradeEngineConfig(engine_version="  ")


def test_enabled_filters_must_not_contain_blank_entries() -> None:
    with pytest.raises(ValueError, match="blank"):
        NoTradeEngineConfig(engine_version="v1", enabled_filters=("time_filter", " "))


def test_valid_custom_config() -> None:
    config = NoTradeEngineConfig(
        engine_version="v1", enabled_filters=("time_filter",), expected_strategy_version="v1",
        filter_parameters={"time_filter": {"windows": []}},
    )
    assert config.enabled_filters == ("time_filter",)
    assert config.filter_parameters["time_filter"] == {"windows": []}


# --- loader -------------------------------------------------------------------------


def test_load_reads_full_yaml(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text(
        "engine_version: v1\n"
        "expected_strategy_version: v1\n"
        "enabled_filters: [time_filter, session_filter]\n"
        "filter_parameters:\n"
        "  time_filter:\n"
        "    example_key: example_value\n"
    )
    config = load_no_trade_engine_config(path)
    assert config.engine_version == "v1"
    assert config.enabled_filters == ("time_filter", "session_filter")
    assert config.filter_parameters["time_filter"]["example_key"] == "example_value"


def test_load_defaults_missing_sections(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text("engine_version: v1\n")
    config = load_no_trade_engine_config(path)
    assert config.enabled_filters is None
    assert config.filter_parameters == {}


def test_load_requires_engine_version(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text("enabled_filters: []\n")
    with pytest.raises(NoTradeEngineConfigError, match="engine_version"):
        load_no_trade_engine_config(path)


def test_load_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(NoTradeEngineConfigError):
        load_no_trade_engine_config(tmp_path / "does_not_exist.yaml")


def test_load_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text("engine_version: [unclosed\n")
    with pytest.raises(NoTradeEngineConfigError, match="Invalid YAML"):
        load_no_trade_engine_config(path)


def test_load_raises_when_top_level_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text("- a\n- list\n")
    with pytest.raises(NoTradeEngineConfigError, match="mapping"):
        load_no_trade_engine_config(path)


def test_load_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text("")
    with pytest.raises(NoTradeEngineConfigError, match="engine_version"):
        load_no_trade_engine_config(path)


def test_load_raises_on_invalid_field_value(tmp_path: Path) -> None:
    path = tmp_path / "no_trade_engine.yaml"
    path.write_text('engine_version: v1\nenabled_filters: ["  "]\n')
    with pytest.raises(NoTradeEngineConfigError, match="invalid no-trade engine config"):
        load_no_trade_engine_config(path)
