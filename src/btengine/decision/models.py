"""Data types for the Decision Engine Framework.

This is a framework, not a strategy: :class:`DecisionStatus` describes
*where a signal sits in the decision pipeline* (has its input been
validated, is it awaiting a decision provider, did one evaluate it) —
never a trading action. No BUY/SELL/ENTER/EXIT vocabulary appears
anywhere in this module, per this task's explicit constraint. Every
place real proprietary decision content would eventually live
(:class:`DecisionOutcome`'s ``metadata``, the not-yet-existing concrete
:class:`~btengine.decision.providers.base.DecisionProvider`
implementations) is an open placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from btengine.scoring.models import ValidationStatus

Severity = Literal["ERROR", "WARNING"]


class DecisionStatus(str, Enum):
    """Where a signal sits in the decision pipeline — never a trading action.

    ``NOT_READY``: input validation failed, or upstream
    :attr:`~btengine.signal_validation.models.ValidatedStrategyState.validation_passed`
    is ``False`` and the engine is configured to require it.
    ``PENDING``: input is valid but no decision provider produced a
    substantive outcome yet — the expected state for every call today,
    since this framework ships no concrete decision logic.
    ``EVALUATED``: at least one decision provider successfully produced
    a non-pending outcome (a framework hook for future providers; never
    reached by anything shipped in this task).
    """

    NOT_READY = "NOT_READY"
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"


@dataclass(frozen=True)
class DecisionOutcome:
    """What one :class:`~btengine.decision.providers.base.DecisionProvider`
    returns for one request.

    A structural placeholder shape — ``status``/``reason``/``metadata``
    are never populated with real BUY/SELL/ENTER/EXIT content by
    anything in this task; that is exactly the proprietary content this
    framework must not invent.
    """

    provider_name: str
    provider_version: str
    status: DecisionStatus
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionValidationIssue:
    """One data-quality or configuration problem found while preparing a :class:`DecisionContext`."""

    severity: Severity
    category: str
    message: str
    provider_name: str | None = None


@dataclass(frozen=True)
class DecisionContext:
    """Standardized output of one :meth:`~btengine.decision.engine.DecisionEngine.decide` call.

    Contains no BUY/SELL logic — only the readiness/validity diagnosis
    this framework is responsible for. ``execution_ready`` is a purely
    structural gate (validation passed *and* at least one provider
    produced a substantive outcome); it never encodes an opinion about
    what should be executed.
    """

    symbol: str
    as_of: datetime
    strategy_version: str
    timestamp: datetime

    decision_status: DecisionStatus
    decision_reason: str
    validation_status: ValidationStatus
    execution_ready: bool

    provider_outcomes: tuple[DecisionOutcome, ...] = ()
    validation_errors: tuple[DecisionValidationIssue, ...] = ()
    validation_warnings: tuple[DecisionValidationIssue, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
