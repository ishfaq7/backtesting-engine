"""Data types for the No Trade Framework.

This is a framework, not a strategy: no filter shipped here contains a
real "don't trade when ..." rule — what market condition, time window,
session, or exchange state should block trading is the strategy owner's
proprietary content. The framework's defining property is **fail-safe
gating**: :attr:`NoTradeAssessment.trading_allowed` is only ever
``True`` when input validation found no errors, at least one filter is
registered, and *every* registered filter explicitly returned
:attr:`FilterVerdict.ALLOW`. An empty framework, an unimplemented
filter (``CANNOT_EVALUATE``), or any validation error all resolve to
``trading_allowed=False`` — an unimplemented gate stays closed, never
open.

Nothing here is a BUY/SELL signal: this framework only answers "is the
system permitted to trade at all right now," never "what trade to make."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from btengine.scoring.models import ValidationStatus

Severity = Literal["ERROR", "WARNING"]


class FilterVerdict(str, Enum):
    """One filter's answer to "may the system trade right now?".

    Deliberately tri-state, mirroring
    :class:`btengine.risk.models.RiskModuleResult`'s tri-state
    ``approved``: ``CANNOT_EVALUATE`` (the permanent state of every
    framework-only stub shipped here) is distinct from an explicit
    ``ALLOW``, so an unimplemented filter can never silently open the
    gate.
    """

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CANNOT_EVALUATE = "CANNOT_EVALUATE"


@dataclass(frozen=True)
class FilterResult:
    """What one :class:`~btengine.no_trade.filters.base.NoTradeFilter` returns."""

    filter_name: str
    filter_version: str
    verdict: FilterVerdict
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class NoTradeValidationIssue:
    """One data-quality or configuration problem found while preparing an assessment."""

    severity: Severity
    category: str
    message: str
    filter_name: str | None = None


@dataclass(frozen=True)
class NoTradeAssessment:
    """Standardized output of one :meth:`~btengine.no_trade.engine.NoTradeEngine.evaluate` call.

    ``blocked_reasons`` collects the ``reason`` of every filter that
    returned ``BLOCK`` *plus* a structural reason whenever the gate is
    closed for framework reasons (no filters registered, a filter could
    not evaluate, validation errors) — the gate never closes silently.
    """

    symbol: str
    as_of: datetime
    strategy_version: str
    timestamp: datetime

    trading_allowed: bool
    blocked_reasons: tuple[str, ...]
    warning_messages: tuple[str, ...]
    active_filters: tuple[str, ...]

    validation_status: ValidationStatus
    filter_results: tuple[FilterResult, ...] = ()
    errors: tuple[NoTradeValidationIssue, ...] = ()
    warnings: tuple[NoTradeValidationIssue, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
