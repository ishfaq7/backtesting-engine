"""The Risk Module contract: one independent module per named risk responsibility.

Each module evaluates exactly one risk concern (position sizing,
leverage, drawdown, ...) for one :class:`~btengine.risk.context.RiskRequest`
and returns one :class:`~btengine.risk.models.RiskModuleResult` — never
another module's concern, never an aggregate verdict (that's
:class:`~btengine.risk.engine.RiskEngine`'s job). Independent modules
are what this task's RESPONSIBILITIES section asks for, and what lets
each be implemented, versioned, tested, and replaced separately via
dependency injection.

Every concrete module in :mod:`btengine.risk.modules` raises
``NotImplementedError`` from :meth:`evaluate` — the actual formulas
(how large a position, how much leverage, where risk limits bite) are
the strategy owner's proprietary risk rules, which this framework must
not invent. The engine converts that into a
``RiskModuleResult(approved=None, ...)`` — "could not evaluate," which
per :class:`~btengine.risk.models.RiskAssessment`'s fail-safe semantics
can never become an approval.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.risk.context import RiskRequest
from btengine.risk.models import RiskModuleResult


class RiskModule(ABC):
    """Evaluates one independent risk concern for one request."""

    @property
    @abstractmethod
    def module_name(self) -> str:
        """A stable, unique name for this module (e.g. ``"position_sizing"``)."""

    @property
    @abstractmethod
    def module_version(self) -> str:
        """Identifies which revision of this module's (not-yet-written)
        risk formula produced a given result — the same versioning
        discipline used throughout this project's engines.
        """

    @abstractmethod
    def evaluate(self, request: RiskRequest) -> RiskModuleResult:
        """Evaluate this module's risk concern for ``request``."""
