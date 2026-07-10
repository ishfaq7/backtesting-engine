"""Position Management Rules — how position size evolves over its
lifetime (pyramiding, scale-ins, netting behavior).

A parameter container, like Risk Management Rules, since these are
settings rather than conditions. Every field defaults to ``None`` — no
pyramiding policy or netting mode is assumed. See
``docs/strategy_spec.md`` §Position Management and
``config/strategy/rules/position_management.yaml`` for the loadable form.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator


class PositionManagementRules(BaseModel):
    """Strategy-level position-sizing-over-time parameters. All values are
    TODO(owner) until explicitly set."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    allow_pyramiding: bool | None = None  # TODO(owner): required
    max_position_scale_ins: int | None = None  # TODO(owner): required if allow_pyramiding
    netting_mode: str | None = None  # TODO(owner): e.g. "NET" | "HEDGE" (open, no default assumed)
    notes: str = ""

    @model_validator(mode="after")
    def _scale_ins_must_be_positive_if_set(self) -> "PositionManagementRules":
        if self.max_position_scale_ins is not None and self.max_position_scale_ins <= 0:
            raise ValueError(
                f"max_position_scale_ins must be positive if set, got {self.max_position_scale_ins}"
            )
        return self
