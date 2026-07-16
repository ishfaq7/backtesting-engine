"""Configuration for the Risk Management Framework.

Every limit in a :class:`RiskProfile` defaults to ``None`` — an
explicit, unset placeholder. Maximum leverage, per-trade risk, drawdown
limits, exposure caps, capital allocation, margin utilization, and
portfolio risk budgets are all proprietary risk-rule content this
framework must not invent; a ``None`` limit means the corresponding
(also not-yet-implemented) risk module has nothing to evaluate against
and reports "could not evaluate," never a silent pass.

"Risk Profiles" (per this task's CONFIGURATION section) are named
:class:`RiskProfile` instances registered in
:attr:`RiskEngineConfig.profiles` with one selected as
:attr:`~RiskEngineConfig.active_profile` — e.g. a "conservative" and an
"aggressive" profile filled in later by the strategy owner, switchable
per engine instance without code changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from btengine.risk.errors import RiskEngineConfigError

_LIMIT_FIELDS = (
    "max_leverage",
    "max_risk_per_trade_pct",
    "max_daily_drawdown_pct",
    "max_total_drawdown_pct",
    "max_exposure_pct",
    "max_capital_allocation_pct",
    "max_margin_utilization_pct",
    "max_portfolio_risk_pct",
)


@dataclass(frozen=True)
class RiskProfile:
    """One named set of risk limits. Every field is an unset placeholder.

    ``*_pct`` fields are fractions of equity (e.g. ``0.02`` = 2%), a
    unit convention only — the values themselves are TODO(owner).
    """

    name: str

    max_leverage: float | None = None  # TODO(owner): required for leverage validation
    max_risk_per_trade_pct: float | None = None  # TODO(owner): required for max-risk validation
    max_daily_drawdown_pct: float | None = None  # TODO(owner): required for daily drawdown protection
    max_total_drawdown_pct: float | None = None  # TODO(owner): required for total drawdown protection
    max_exposure_pct: float | None = None  # TODO(owner): required for exposure management
    max_capital_allocation_pct: float | None = None  # TODO(owner): required for capital allocation
    max_margin_utilization_pct: float | None = None  # TODO(owner): required for margin validation
    max_portfolio_risk_pct: float | None = None  # TODO(owner): required for portfolio risk

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("profile name must not be empty")
        for field_name in _LIMIT_FIELDS:
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be > 0 when set, got {value}")


@dataclass(frozen=True)
class RiskEngineConfig:
    """Tunable parameters for :class:`~btengine.risk.engine.RiskEngine`."""

    engine_version: str

    # Named risk profiles; active_profile selects which one applies.
    profiles: dict[str, RiskProfile] = field(default_factory=dict)
    active_profile: str | None = None

    # TODO(owner): set to enable the "strategy version mismatch" check
    # against DecisionContext.strategy_version. None = not checked.
    expected_strategy_version: str | None = None

    def __post_init__(self) -> None:
        if not self.engine_version.strip():
            raise ValueError("engine_version must not be empty")
        for key, profile in self.profiles.items():
            if key != profile.name:
                raise ValueError(
                    f"profile registered under key {key!r} has mismatched name {profile.name!r}"
                )
        if self.active_profile is not None and self.active_profile not in self.profiles:
            raise ValueError(
                f"active_profile {self.active_profile!r} is not a registered profile "
                f"(registered: {sorted(self.profiles)})"
            )

    @property
    def resolved_profile(self) -> RiskProfile | None:
        """The currently active :class:`RiskProfile`, or ``None`` if unset."""
        if self.active_profile is None:
            return None
        return self.profiles[self.active_profile]


def load_risk_engine_config(path: Path | str) -> RiskEngineConfig:
    """Load a :class:`RiskEngineConfig` from a YAML file.

    Follows the same "missing value is a placeholder, not an error"
    convention as every prior loader in this project.
    """
    path = Path(path)
    try:
        raw = path.read_text()
    except OSError as exc:
        raise RiskEngineConfigError(f"Could not read risk engine config {path}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise RiskEngineConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise RiskEngineConfigError(
            f"Expected a YAML mapping at the top level of {path}, got {type(data).__name__}"
        )

    engine_version = data.get("engine_version")
    if not engine_version:
        raise RiskEngineConfigError(f"{path}: engine_version is required")

    try:
        profiles = {
            name: RiskProfile(name=name, **(profile_data or {}))
            for name, profile_data in (data.get("profiles") or {}).items()
        }
        return RiskEngineConfig(
            engine_version=engine_version,
            profiles=profiles,
            active_profile=data.get("active_profile"),
            expected_strategy_version=data.get("expected_strategy_version"),
        )
    except (ValueError, TypeError) as exc:
        raise RiskEngineConfigError(f"{path}: invalid risk engine config: {exc}") from exc
