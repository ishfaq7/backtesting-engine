from datetime import timedelta
from pathlib import Path

import pytest

from btengine.signal_validation.config import SignalValidationConfig, load_signal_validation_config
from btengine.signal_validation.errors import SignalValidationConfigError


def test_defaults_are_valid() -> None:
    config = SignalValidationConfig(engine_version="v1")
    assert config.expected_score_version is None
    assert config.max_staleness is None
    assert config.max_timestamp_skew is None
    assert config.min_confidence is None
    assert config.min_completeness_ratio is None
    assert config.required_providers is None
    assert config.history_window == 20


def test_engine_version_is_required_and_non_empty() -> None:
    with pytest.raises(ValueError, match="engine_version"):
        SignalValidationConfig(engine_version="")
    with pytest.raises(ValueError, match="engine_version"):
        SignalValidationConfig(engine_version="   ")


def test_max_staleness_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_staleness"):
        SignalValidationConfig(engine_version="v1", max_staleness=timedelta(0))


def test_max_timestamp_skew_must_be_non_negative() -> None:
    with pytest.raises(ValueError, match="max_timestamp_skew"):
        SignalValidationConfig(engine_version="v1", max_timestamp_skew=timedelta(seconds=-1))


def test_max_timestamp_skew_of_zero_is_valid() -> None:
    config = SignalValidationConfig(engine_version="v1", max_timestamp_skew=timedelta(0))
    assert config.max_timestamp_skew == timedelta(0)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_min_confidence_must_be_between_zero_and_one(value: float) -> None:
    with pytest.raises(ValueError, match="min_confidence"):
        SignalValidationConfig(engine_version="v1", min_confidence=value)


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_min_completeness_ratio_must_be_between_zero_and_one(value: float) -> None:
    with pytest.raises(ValueError, match="min_completeness_ratio"):
        SignalValidationConfig(engine_version="v1", min_completeness_ratio=value)


def test_required_providers_must_be_known_names() -> None:
    with pytest.raises(ValueError, match="unknown"):
        SignalValidationConfig(engine_version="v1", required_providers=("not_a_provider",))


def test_history_window_must_be_at_least_one() -> None:
    with pytest.raises(ValueError, match="history_window"):
        SignalValidationConfig(engine_version="v1", history_window=0)


def test_valid_custom_config() -> None:
    config = SignalValidationConfig(
        engine_version="v1", expected_score_version="v1", max_staleness=timedelta(hours=1),
        max_timestamp_skew=timedelta(minutes=5), min_confidence=0.5, min_completeness_ratio=0.75,
        required_providers=("funding", "liquidity"), history_window=10,
    )
    assert config.max_staleness == timedelta(hours=1)
    assert config.required_providers == ("funding", "liquidity")


# --- load_signal_validation_config -----------------------------------------------


def test_load_reads_full_yaml(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text(
        "engine_version: v1\n"
        "expected_score_version: v1\n"
        "max_staleness_seconds: 3600\n"
        "max_timestamp_skew_seconds: 300\n"
        "min_confidence: 0.5\n"
        "min_completeness_ratio: 0.75\n"
        "required_providers: [funding]\n"
        "history_window: 5\n"
    )
    config = load_signal_validation_config(path)
    assert config.engine_version == "v1"
    assert config.max_staleness == timedelta(seconds=3600)
    assert config.max_timestamp_skew == timedelta(seconds=300)
    assert config.min_confidence == 0.5
    assert config.required_providers == ("funding",)
    assert config.history_window == 5


def test_load_defaults_missing_sections(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("engine_version: v1\n")
    config = load_signal_validation_config(path)
    assert config.max_staleness is None
    assert config.required_providers is None
    assert config.history_window == 20


def test_load_requires_engine_version(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("min_confidence: 0.5\n")
    with pytest.raises(SignalValidationConfigError, match="engine_version"):
        load_signal_validation_config(path)


def test_load_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SignalValidationConfigError):
        load_signal_validation_config(tmp_path / "does_not_exist.yaml")


def test_load_raises_on_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("engine_version: [unclosed\n")
    with pytest.raises(SignalValidationConfigError, match="Invalid YAML"):
        load_signal_validation_config(path)


def test_load_raises_when_top_level_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("- just\n- a\n- list\n")
    with pytest.raises(SignalValidationConfigError, match="mapping"):
        load_signal_validation_config(path)


def test_load_handles_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("")
    with pytest.raises(SignalValidationConfigError, match="engine_version"):
        load_signal_validation_config(path)


def test_load_raises_on_invalid_field_value(tmp_path: Path) -> None:
    path = tmp_path / "signal_validation.yaml"
    path.write_text("engine_version: v1\nmin_confidence: 5.0\n")
    with pytest.raises(SignalValidationConfigError, match="invalid signal validation config"):
        load_signal_validation_config(path)
