"""Trade Management Rules — adjustments to an already-open position
(trailing stops, partial exits, breakeven moves), as opposed to Exit
Rules which close it outright.

Each rule pairs a generic trigger condition with a named, owner-defined
action. The action itself is an open string (not an enum), plus a free
numeric parameter map — this framework does not assume what management
actions exist or how they behave; it only fixes that "a trigger leads to
a named action with parameters." See ``docs/strategy_spec.md`` §Trade
Management and ``config/strategy/rules/trade_management.yaml`` for the
loadable form.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from btengine.strategy.rules.primitives import RuleCondition


class TradeManagementAction(BaseModel):
    """One trigger-condition-to-action pairing."""

    model_config = ConfigDict(extra="forbid")

    name: str
    trigger: RuleCondition
    action: str | None = None  # TODO(owner): e.g. "MOVE_STOP_TO_BREAKEVEN" | "PARTIAL_EXIT" (open, no enum assumed)
    action_params: dict[str, float] = Field(default_factory=dict)
    enabled: bool = True


class TradeManagementRules(BaseModel):
    """A named collection of in-trade management actions."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    actions: list[TradeManagementAction] = Field(default_factory=list)
    notes: str = ""
