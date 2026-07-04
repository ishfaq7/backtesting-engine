"""Strategy profile presets — a data container, not decision logic.

A :class:`StrategyProfile` is a named bundle of generic, strategy-agnostic
risk/sizing envelope parameters (e.g. "how much risk per trade is this
profile allowed to take"). It contains no rules about *when* to trade —
whether and how a strategy plugin honors these values is entirely up to
that plugin; the engine does not read or enforce them.

No concrete numeric presets are provided here deliberately: choosing actual
risk percentages/limits for Aggressive/Balanced/Conservative is a strategy
decision, out of scope for this architecture pass. This module only fixes
the shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StrategyProfileName(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"


@dataclass(frozen=True)
class StrategyProfile:
    """A named preset of risk/sizing envelope parameters."""

    name: StrategyProfileName
    max_risk_per_trade_pct: float
    max_concurrent_positions: int
    max_portfolio_exposure_pct: float

    def __post_init__(self) -> None:
        if self.max_risk_per_trade_pct <= 0:
            raise ValueError("max_risk_per_trade_pct must be positive")
        if self.max_concurrent_positions <= 0:
            raise ValueError("max_concurrent_positions must be positive")
        if self.max_portfolio_exposure_pct <= 0:
            raise ValueError("max_portfolio_exposure_pct must be positive")
