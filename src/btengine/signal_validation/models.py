"""Data types for the Signal Validation Engine.

This engine sits between the Scoring Engine and the (not-yet-built)
Decision Engine and does exactly one job: check the quality and
integrity of a :class:`~btengine.scoring.models.StrategyScore` and its
four upstream analyses, and report what it found. It never edits a
score, never computes a new one, and never decides anything about a
trade — every field here is a diagnostic, not a decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

from btengine.scoring.models import StrategyScore

Severity = Literal["ERROR", "WARNING"]


@dataclass(frozen=True)
class SignalValidationIssue:
    """One data-quality or configuration problem found during validation.

    ``category`` groups issues by which of the ten named responsibilities
    produced them (e.g. ``"freshness"``, ``"consistency"``,
    ``"structural"``, ``"confidence"``, ``"completeness"``, ``"version"``,
    ``"duplicate"``, ``"sequencing"``) — used to compute
    :class:`DataIntegrityStatus` without parsing free-text messages.
    """

    severity: Severity
    category: str
    message: str
    provider_name: str | None = None


class ConfidenceStatus(str, Enum):
    """A structural read on :attr:`~btengine.scoring.models.StrategyScore.confidence`."""

    VALID = "VALID"
    LOW = "LOW"  # present, structurally valid, but below a configured min_confidence
    INVALID = "INVALID"  # NaN/infinite/outside [0, 1]
    UNKNOWN = "UNKNOWN"  # confidence is None


class ModuleHealthStatus(str, Enum):
    """Per-provider health, combining the Scoring Engine's own
    :class:`~btengine.scoring.models.FeatureStatus` with this engine's
    own freshness check.
    """

    HEALTHY = "HEALTHY"
    MISSING = "MISSING"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INVALID = "INVALID"
    STALE = "STALE"


class DataIntegrityStatus(str, Enum):
    """Overall rollup of every issue found, prioritized: freshness first
    (most actionable), then consistency/structural/sequencing problems,
    then any other error, else valid.
    """

    VALID = "VALID"
    STALE = "STALE"
    INCONSISTENT = "INCONSISTENT"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FeatureCompleteness:
    """How many of the four score providers actually contributed a value.

    ``is_sufficient`` stays ``None`` (unclassified) until
    :attr:`~btengine.signal_validation.config.SignalValidationConfig.min_completeness_ratio`
    is configured — ``completeness_ratio`` itself is always computed.
    """

    available_providers: tuple[str, ...]
    missing_providers: tuple[str, ...]
    completeness_ratio: float
    is_sufficient: bool | None


@dataclass(frozen=True)
class ValidatedStrategyState:
    """Standardized output of one :meth:`~btengine.signal_validation.engine.SignalValidationEngine.validate` call.

    ``score`` is the exact, unmodified :class:`StrategyScore` this state
    was computed from — this engine only ever reads it, never edits or
    replaces any of its fields.
    """

    symbol: str
    as_of: datetime
    strategy_version: str

    score: StrategyScore

    validation_passed: bool
    validation_errors: tuple[SignalValidationIssue, ...]
    validation_warnings: tuple[SignalValidationIssue, ...]

    confidence_status: ConfidenceStatus
    feature_completeness: FeatureCompleteness
    module_health: dict[str, ModuleHealthStatus] = field(default_factory=dict)
    data_integrity: DataIntegrityStatus = DataIntegrityStatus.VALID
