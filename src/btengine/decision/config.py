"""Configuration for the Decision Engine Framework.

Every strategy-shaped field defaults to ``None`` or an empty
collection — an explicit, unset placeholder, exactly like every
upstream analysis/scoring/validation config. ``require_validation_passed``
and ``history_window`` are the two fields with a real, non-``None``
default: the former is an operational safety switch ("don't hand
unvalidated data to a decision provider"), not a trading rule, and the
latter is a generic technical buffer size, like an SMA period elsewhere
in this codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from btengine.decision.errors import DecisionEngineConfigError


@dataclass(frozen=True)
class DecisionEngineConfig:
    """Tunable parameters for :class:`~btengine.decision.engine.DecisionEngine`."""

    engine_version: str

    # TODO(owner): set to enable the "strategy version mismatch" check
    # against ValidatedStrategyState.strategy_version. None = not checked.
    expected_strategy_version: str | None = None

    # None = no decision provider is required; the engine runs happily
    # (in a permanently PENDING state) with zero providers configured -
    # the expected condition until proprietary decision logic exists.
    required_providers: tuple[str, ...] | None = None

    # Deterministic provider evaluation order. A provider name absent
    # here sorts after every explicitly-prioritized one (see
    # order_provider_names_by_priority()). Empty = no explicit ordering;
    # providers run in the order they were supplied to the engine.
    provider_priorities: dict[str, int] = field(default_factory=dict)

    # An operational safety default, not a trading rule: whether an
    # upstream ValidatedStrategyState.validation_passed == False forces
    # DecisionStatus.NOT_READY regardless of what decision providers
    # might otherwise produce.
    require_validation_passed: bool = True

    # Bounded per-symbol history size used by the engine's own
    # "duplicate processing" check.
    history_window: int = 20

    def __post_init__(self) -> None:
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")
        if self.history_window < 1:
            raise ValueError(f"history_window must be >= 1, got {self.history_window}")


def order_provider_names_by_priority(
    provider_names: list[str], priorities: dict[str, int]
) -> list[str]:
    """Return ``provider_names`` ordered by ascending configured priority.

    A name with no entry in ``priorities`` sorts after every
    explicitly-prioritized name; ties (including "none prioritized")
    break alphabetically, so the result is always deterministic.
    """

    def sort_key(name: str) -> tuple[int, int, str]:
        priority = priorities.get(name)
        return (0, priority, name) if priority is not None else (1, 0, name)

    return sorted(provider_names, key=sort_key)


def load_decision_engine_config(path: Path | str) -> DecisionEngineConfig:
    """Load a :class:`DecisionEngineConfig` from a YAML file.

    Follows the same "missing value is a placeholder, not an error"
    convention as every prior loader in this project
    (``load_strategy_spec``, ``load_scoring_engine_config``,
    ``load_signal_validation_config``).
    """
    path = Path(path)
    try:
        raw = path.read_text()
    except OSError as exc:
        raise DecisionEngineConfigError(f"Could not read decision engine config {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise DecisionEngineConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise DecisionEngineConfigError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )

    engine_version = data.get("engine_version")
    if not engine_version:
        raise DecisionEngineConfigError(f"{path}: engine_version is required")

    required_providers = data.get("required_providers")
    if required_providers is not None:
        required_providers = tuple(required_providers)

    try:
        return DecisionEngineConfig(
            engine_version=engine_version,
            expected_strategy_version=data.get("expected_strategy_version"),
            required_providers=required_providers,
            provider_priorities=dict(data.get("provider_priorities") or {}),
            require_validation_passed=data.get("require_validation_passed", True),
            history_window=data.get("history_window", 20),
        )
    except (ValueError, TypeError) as exc:
        raise DecisionEngineConfigError(f"{path}: invalid decision engine config: {exc}") from exc
