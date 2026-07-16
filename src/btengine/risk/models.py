"""Data types for the Risk Management Framework.

This is a framework, not a strategy: every numeric field a real risk
formula would eventually fill in (:attr:`RiskAssessment.position_size`,
``leverage_allowed``, ``max_risk_allowed``, ``portfolio_risk``) is
optional and stays ``None`` until a concrete, owner-supplied
:class:`~btengine.risk.modules.base.RiskModule` implementation exists.
``risk_approved`` can never be ``True`` without one — an unimplemented
risk framework must fail safe (nothing approved), never fail open.

The three ``*Snapshot`` input types are this framework's own minimal,
frozen input shapes — deliberately decoupled from the live, mutable
:class:`btengine.backtest.portfolio_state.PortfolioState` /
:class:`btengine.backtest.position_manager.Position` classes (which are
simulation bookkeeping, not validated inputs) so this engine stays
reusable across backtesting, demo trading, and live trading, and so its
own validator can detect malformed values a live class would never
produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from btengine.scoring.models import ValidationStatus

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class PositionStateSnapshot:
    """One symbol's current position, as given to the risk engine."""

    symbol: str
    quantity: float  # signed: positive = long, negative = short
    avg_entry_price: float
    unrealized_pnl: float
    leverage: float | None = None  # None = not known/not applicable


@dataclass(frozen=True)
class PortfolioStateSnapshot:
    """The account's current state, as given to the risk engine.

    ``daily_realized_pnl`` / ``peak_equity`` are optional context for
    the (not-yet-implemented) drawdown-protection modules — ``None``
    simply means the caller doesn't track them yet.
    """

    cash: float
    equity: float
    positions: tuple[PositionStateSnapshot, ...] = ()
    daily_realized_pnl: float | None = None
    peak_equity: float | None = None
    margin_used: float | None = None


@dataclass(frozen=True)
class MarketDataSnapshot:
    """Minimal current-market context for one symbol.

    Only what generic risk arithmetic could ever need (a price to value
    a position with; an optional volatility measure for the future
    Volatility Risk module) — never a signal or an analytical judgment.
    """

    symbol: str
    price: float
    timestamp: datetime
    volatility: float | None = None


class ExposureStatus(str, Enum):
    """A structural read on current exposure relative to configured limits.

    ``UNKNOWN`` whenever no limit is configured or no module computed a
    value — never silently assumed acceptable.
    """

    WITHIN_LIMITS = "WITHIN_LIMITS"
    EXCEEDED = "EXCEEDED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RiskValidationIssue:
    """One data-quality or configuration problem found during risk preparation."""

    severity: Severity
    category: str
    message: str
    module_name: str | None = None


@dataclass(frozen=True)
class RiskModuleResult:
    """What one :class:`~btengine.risk.modules.base.RiskModule` returns.

    ``approved`` is tri-state: ``None`` means "this module could not
    evaluate" (the permanent state of every framework-only stub shipped
    here) — deliberately distinct from an explicit ``False`` rejection,
    so an unimplemented module never silently passes as approval.
    """

    module_name: str
    module_version: str
    approved: bool | None
    value: float | None
    reason: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RiskAssessment:
    """Standardized output of one :meth:`~btengine.risk.engine.RiskEngine.assess` call.

    ``risk_approved`` follows fail-safe semantics: it is only ``True``
    when validation found no errors *and* every registered module
    explicitly approved (``approved is True``) *and* at least one module
    is registered — an empty or unimplemented framework never approves
    anything by default.
    """

    symbol: str
    as_of: datetime
    strategy_version: str
    timestamp: datetime

    risk_approved: bool
    position_size: float | None
    leverage_allowed: float | None
    max_risk_allowed: float | None
    exposure_status: ExposureStatus
    portfolio_risk: float | None

    validation_status: ValidationStatus
    module_results: tuple[RiskModuleResult, ...] = ()
    errors: tuple[RiskValidationIssue, ...] = ()
    warnings: tuple[RiskValidationIssue, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
