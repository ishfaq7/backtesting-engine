"""The Validation Check contract.

Each check is one independent, named, stateless rule that inspects a
:class:`~btengine.signal_validation.context.ValidationContext` and
returns whatever issues it finds. This is the extension seam this task
asks for ("Prepare extension points for: AI Validation, Ensemble
Validation, Rule Conflict Detection, Cross-Timeframe Validation,
Multi-Coin Validation, Portfolio Validation" — see
``docs/SIGNAL_VALIDATION_ENGINE.md`` §Future Extension Points): a new
check is a new class implementing this interface, added to the list
:class:`~btengine.signal_validation.engine.SignalValidationEngine` is
constructed with — no change to the engine itself.

Unlike :mod:`btengine.scoring.providers`, checks in
:mod:`btengine.signal_validation.checks.builtin` are fully implemented,
not framework-only stubs — this task asks for a working, production-grade
validation layer, not a placeholder for proprietary content.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.signal_validation.context import ValidationContext
from btengine.signal_validation.models import SignalValidationIssue


class ValidationCheck(ABC):
    """One independent, stateless check contributing issues to a validation run."""

    @property
    @abstractmethod
    def check_name(self) -> str:
        """A stable, unique name for this check (used for logging/introspection)."""

    @abstractmethod
    def run(self, context: ValidationContext) -> list[SignalValidationIssue]:
        """Return every issue this check finds for ``context`` (empty if none)."""
