"""Risk Management Rules — position sizing and exposure limits.

Unlike the condition-based rule categories, risk management is naturally a
set of *parameters* rather than conditions, so this module is a plain
settings container instead of a :class:`~btengine.strategy.rules.primitives.RuleSet`.
Every field defaults to ``None`` (an explicit "not yet specified"
placeholder) — no risk percentage, leverage limit, or loss cap is assumed.
See ``docs/strategy_spec.md`` §Risk Rules and
``config/strategy/rules/risk_management.yaml`` for the loadable form.

Distinct from the Core Backtesting Engine's own generic, strategy-agnostic
risk checks (position/order sanity validation in
:class:`~btengine.backtest.order_manager.OrderManager`) — these are the
strategy's own, proprietary risk parameters, consumed only within the
strategy plugin.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class RiskManagementRules(BaseModel):
    """Strategy-level risk/sizing parameters. All values are TODO(owner)
    until explicitly set."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    max_risk_per_trade_pct: float | None = None  # TODO(owner): required
    max_leverage: float | None = None  # TODO(owner): required
    max_concurrent_positions: int | None = None  # TODO(owner): required
    max_daily_loss_pct: float | None = None  # TODO(owner): required
    stop_loss_type: str | None = None  # TODO(owner): e.g. "FIXED_PCT" | "ATR_MULTIPLE" (open, no enum assumed)
    notes: str = ""

    @model_validator(mode="after")
    def _percentages_must_be_positive_if_set(self) -> "RiskManagementRules":
        for field_name in ("max_risk_per_trade_pct", "max_daily_loss_pct"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise ValueError(f"{field_name} must be positive if set, got {value}")
        if self.max_leverage is not None and self.max_leverage <= 0:
            raise ValueError(f"max_leverage must be positive if set, got {self.max_leverage}")
        if self.max_concurrent_positions is not None and self.max_concurrent_positions <= 0:
            raise ValueError(
                f"max_concurrent_positions must be positive if set, got {self.max_concurrent_positions}"
            )
        return self
