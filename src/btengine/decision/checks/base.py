"""The Decision Validation Check contract.

Structurally identical in shape to
:class:`btengine.signal_validation.checks.base.ValidationCheck` (one
independent, stateless, named check), but defined fresh for this
package rather than shared — the same "each validation layer owns its
own issue/check vocabulary" convention used by every validator in this
project (feature pipeline, funding, open interest, premium/discount,
liquidity, scoring, signal validation). The Decision Engine
independently re-validates its inputs rather than only trusting the
Signal Validation Engine's own verdict — deliberate defense-in-depth,
not redundant busywork.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.decision.context import DecisionRequest
from btengine.decision.models import DecisionValidationIssue


class DecisionValidationCheck(ABC):
    """One independent, stateless check contributing issues to a decision-preparation run."""

    @property
    @abstractmethod
    def check_name(self) -> str:
        """A stable, unique name for this check (used for logging/introspection)."""

    @abstractmethod
    def run(self, request: DecisionRequest) -> list[DecisionValidationIssue]:
        """Return every issue this check finds for ``request`` (empty if none)."""
