"""Data types for the Scoring Engine Framework.

This is a framework, not a strategy: every numeric field a real scoring
formula would eventually fill in (``ScoreComponent.value``,
``StrategyScore.total_score``) is optional and stays ``None`` until a
concrete, owner-supplied :class:`~btengine.scoring.providers.base.ScoreProvider`
implementation exists. No field here computes, assumes, or hardcodes a
weight, threshold, or BUY/SELL interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal

Severity = Literal["ERROR", "WARNING"]


class FeatureStatus(str, Enum):
    """Why one input's :class:`ScoreComponent` does or doesn't have a value.

    Distinguishing these four cases is what makes the framework
    "explainable": a caller can always tell *why* ``funding_score`` is
    ``None`` — because no ``FundingAnalysis`` was supplied at all
    (``MISSING``), because a provider exists but hasn't been implemented
    yet (``NOT_IMPLEMENTED`` — true for every provider shipped in this
    framework), because the provider ran but produced something invalid
    (``INVALID``), or because it all worked (``AVAILABLE``).
    """

    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    INVALID = "INVALID"


class ValidationStatus(str, Enum):
    """The overall rollup of every :class:`~btengine.scoring.validation.StrategyScoreValidationIssue`."""

    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ScoreComponent:
    """One provider's standardized contribution to a :class:`StrategyScore`.

    ``value`` and ``weight`` are ``None`` until a concrete provider
    implementation and an explicit configured weight exist — this
    framework never invents either. ``confidence`` is copied from the
    upstream analysis's own ``confidence_level`` (a data-sufficiency
    measure, not a trading-confidence score — see the analysis modules'
    own documentation). ``explanation`` is free text a provider can use
    to describe *why* it produced (or couldn't produce) its value —
    "Explainable Scoring."
    """

    provider_name: str
    provider_version: str
    value: float | None
    weight: float | None
    confidence: float | None
    explanation: str = ""


@dataclass(frozen=True)
class StrategyScoreValidationIssue:
    """One data-quality or configuration problem found while assembling a :class:`StrategyScore`.

    Defined here (not in :mod:`~btengine.scoring.validation`) so
    ``StrategyScore`` can embed the full issue list directly — part of
    "Explainable Scoring": the output itself carries *why* any field is
    ``None`` or ``validation_status`` isn't ``VALID``.
    """

    severity: Severity
    message: str
    provider_name: str | None = None


@dataclass(frozen=True)
class StrategyScore:
    """Standardized, versioned output of one :class:`~btengine.scoring.engine.ScoringEngine.score` call.

    ``total_score`` and ``confidence`` are ``None`` whenever they cannot
    be honestly computed (a required weight or component is missing, or
    validation found an ``ERROR``-severity issue) rather than falling
    back to a partial or default number.
    """

    symbol: str
    as_of: datetime
    score_version: str

    funding_score: ScoreComponent | None
    oi_score: ScoreComponent | None
    premium_discount_score: ScoreComponent | None
    liquidity_score: ScoreComponent | None

    total_score: float | None
    confidence: float | None

    feature_status: dict[str, FeatureStatus] = field(default_factory=dict)
    validation_status: ValidationStatus = ValidationStatus.VALID
    validation_issues: tuple[StrategyScoreValidationIssue, ...] = ()
