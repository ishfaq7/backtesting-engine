"""The Risk Validation Check contract.

Structurally the same shape as the Signal Validation and Decision
Engines' own check interfaces, defined fresh for this package — the
"each validation layer owns its own issue/check vocabulary" convention
used by every validator in this project. Checks validate the *inputs*
to a risk assessment (a malformed portfolio snapshot, a missing
configuration); they never evaluate a risk *rule* — that's a
:class:`~btengine.risk.modules.base.RiskModule`'s job, and none of
those are implemented in this framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.risk.context import RiskRequest
from btengine.risk.models import RiskValidationIssue


class RiskValidationCheck(ABC):
    """One independent, stateless check contributing issues to a risk-preparation run."""

    @property
    @abstractmethod
    def check_name(self) -> str:
        """A stable, unique name for this check (used for logging/introspection)."""

    @abstractmethod
    def run(self, request: RiskRequest) -> list[RiskValidationIssue]:
        """Return every issue this check finds for ``request`` (empty if none)."""
