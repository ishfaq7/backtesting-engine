"""Loads a :class:`~btengine.strategy.spec.StrategySpec` from a directory
of YAML files.

Expects the ``config/strategy/`` layout: a top-level ``strategy.yaml``
(name/version/profile/known_assumptions/todo), a ``scoring.yaml``, and one
``rules/<category>.yaml`` per rule category. A missing file is treated as
"nothing configured yet" (an empty mapping) rather than an error, so a
partially-filled-in spec still loads — schema validation (required fields
like ``scoring.version``) is what surfaces genuinely missing information,
not file presence.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from btengine.strategy.spec import StrategySpec
from btengine.strategy.spec_errors import SpecLoadError

_RULE_FILENAME_BY_FIELD: dict[str, str] = {
    "funding_rate_rules": "funding_rate.yaml",
    "open_interest_rules": "open_interest.yaml",
    "premium_discount_rules": "premium_discount.yaml",
    "liquidity_rules": "liquidity.yaml",
    "market_structure_rules": "market_structure.yaml",
    "cvd_rules": "cvd.yaml",
    "atr_rules": "atr.yaml",
    "entry_rules": "entry.yaml",
    "exit_rules": "exit.yaml",
    "risk_management_rules": "risk_management.yaml",
    "no_trade_conditions": "no_trade.yaml",
    "trade_management_rules": "trade_management.yaml",
    "position_management_rules": "position_management.yaml",
    "session_filters": "session_filters.yaml",
    "market_condition_filters": "market_condition_filters.yaml",
}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text()
    except OSError as exc:
        raise SpecLoadError(f"Could not read spec file {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SpecLoadError(f"Invalid YAML in {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise SpecLoadError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )
    return data


def load_strategy_spec(root: Path | str) -> StrategySpec:
    """Load a complete :class:`StrategySpec` from ``root`` (a directory
    following the ``config/strategy/`` layout).
    """
    root = Path(root)
    strategy_file = root / "strategy.yaml"
    scoring_file = root / "scoring.yaml"
    rules_dir = root / "rules"

    top_level = _read_yaml(strategy_file) if strategy_file.exists() else {}
    scoring_data = _read_yaml(scoring_file) if scoring_file.exists() else {}

    rule_data: dict[str, Any] = {}
    for field_name, filename in _RULE_FILENAME_BY_FIELD.items():
        rule_path = rules_dir / filename
        rule_data[field_name] = _read_yaml(rule_path) if rule_path.exists() else {}

    payload = {**top_level, "scoring": scoring_data, **rule_data}
    try:
        return StrategySpec(**payload)
    except ValidationError as exc:
        raise SpecLoadError(f"Strategy spec at {root} failed schema validation: {exc}") from exc
