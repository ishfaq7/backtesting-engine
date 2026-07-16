"""Configuration for the No Trade Framework.

Every rule-shaped field defaults to ``None``/empty — an explicit, unset
placeholder, matching every prior engine config in this project. Which
filters are enabled, what sessions or time windows should block
trading, and which exchanges are acceptable are all proprietary
choices; an unset value means the corresponding (also unimplemented)
filter has nothing to evaluate against, and the fail-safe gate stays
closed regardless.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from btengine.no_trade.errors import NoTradeEngineConfigError


@dataclass(frozen=True)
class NoTradeEngineConfig:
    """Tunable parameters for :class:`~btengine.no_trade.engine.NoTradeEngine`."""

    engine_version: str

    # None = every registered filter runs. A tuple restricts evaluation
    # to just the named filters (a registered filter absent from the
    # list is skipped, and skipping is recorded in the assessment
    # metadata) - "Configurable filters" per this task's CONFIGURATION
    # section, without code changes.
    enabled_filters: tuple[str, ...] | None = None

    # TODO(owner): set to enable the "strategy version mismatch" check
    # against DecisionContext.strategy_version. None = not checked.
    expected_strategy_version: str | None = None

    # TODO(owner): free-form parameters for future filter implementations
    # (e.g. blocked session names for SessionFilter, allowed exchanges
    # for ExchangeFilter, time windows for TimeFilter). This framework
    # defines no keys - each future filter documents and reads its own.
    filter_parameters: dict[str, dict[str, object]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")
        if self.enabled_filters is not None and any(
            not name.strip() for name in self.enabled_filters
        ):
            raise ValueError("enabled_filters must not contain blank entries")


def load_no_trade_engine_config(path: Path | str) -> NoTradeEngineConfig:
    """Load a :class:`NoTradeEngineConfig` from a YAML file.

    Follows the same "missing value is a placeholder, not an error"
    convention as every prior loader in this project.
    """
    path = Path(path)
    try:
        raw = path.read_text()
    except OSError as exc:
        raise NoTradeEngineConfigError(f"Could not read no-trade engine config {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise NoTradeEngineConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise NoTradeEngineConfigError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )

    engine_version = data.get("engine_version")
    if not engine_version:
        raise NoTradeEngineConfigError(f"{path}: engine_version is required")

    enabled_filters = data.get("enabled_filters")
    if enabled_filters is not None:
        enabled_filters = tuple(enabled_filters)

    try:
        return NoTradeEngineConfig(
            engine_version=engine_version,
            enabled_filters=enabled_filters,
            expected_strategy_version=data.get("expected_strategy_version"),
            filter_parameters=dict(data.get("filter_parameters") or {}),
        )
    except (ValueError, TypeError) as exc:
        raise NoTradeEngineConfigError(f"{path}: invalid no-trade engine config: {exc}") from exc
