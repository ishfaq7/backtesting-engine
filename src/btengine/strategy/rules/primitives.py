"""Generic, domain-neutral building blocks every rule category is built from.

This module defines *how* a rule is expressed — a named comparison against
a computed feature, combined with other comparisons by AND/OR — never
*what* any rule should say. No field here has a default that represents an
actual trading value: ``value``, ``value_high``, and ``feature`` are all
required-but-unset (``None``/empty) until the strategy owner supplies them,
so an incomplete spec fails validation instead of silently running with an
invented number.

Every one of the 16 rule categories in ``docs/strategy_spec.md`` is built
by combining these two primitives (:class:`RuleCondition`,
:class:`RuleSet`) — see ``btengine/strategy/rules/*.py``.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComparisonOperator(str, Enum):
    """How a condition's feature value is compared against its threshold(s)."""

    GT = "GT"  # feature > value
    GTE = "GTE"  # feature >= value
    LT = "LT"  # feature < value
    LTE = "LTE"  # feature <= value
    EQ = "EQ"  # feature == value
    NEQ = "NEQ"  # feature != value
    BETWEEN = "BETWEEN"  # value <= feature <= value_high


class RuleCombinationLogic(str, Enum):
    """How multiple conditions in one :class:`RuleSet` combine."""

    ALL = "ALL"  # every enabled condition must hold (logical AND)
    ANY = "ANY"  # at least one enabled condition must hold (logical OR)
    CUSTOM = "CUSTOM"  # combined elsewhere (e.g. by a scoring model), not by simple AND/OR


class RuleCondition(BaseModel):
    """One atomic, named comparison: ``<feature> <operator> <value>``.

    Pure structure. ``feature``, ``value`` (and ``value_high`` for
    ``BETWEEN``) must be supplied by the strategy owner — TODO placeholders
    left as ``None``/empty are intentional and are what
    :mod:`~btengine.strategy.spec_validation` flags as incomplete.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    feature: str = ""  # TODO(owner): which computed feature/value this condition reads
    operator: ComparisonOperator
    value: float | None = None  # TODO(owner): required threshold value
    value_high: float | None = None  # only used when operator == BETWEEN
    enabled: bool = True
    description: str = ""

    @model_validator(mode="after")
    def _between_requires_value_high(self) -> "RuleCondition":
        if self.operator == ComparisonOperator.BETWEEN:
            if self.value is not None and self.value_high is not None and self.value_high <= self.value:
                raise ValueError(
                    f"condition {self.name!r}: value_high ({self.value_high}) must be "
                    f"greater than value ({self.value}) for a BETWEEN condition"
                )
        elif self.value_high is not None:
            raise ValueError(
                f"condition {self.name!r}: value_high is only meaningful for a BETWEEN condition"
            )
        return self


class RuleSet(BaseModel):
    """A named, independently enable-able collection of conditions."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    combination_logic: RuleCombinationLogic = RuleCombinationLogic.ALL
    conditions: list[RuleCondition] = Field(default_factory=list)
    notes: str = ""
