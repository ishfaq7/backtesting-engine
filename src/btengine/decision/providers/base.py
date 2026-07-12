"""The Decision Provider contract: "Support multiple decision providers."

A `DecisionProvider` turns one prepared
:class:`~btengine.decision.context.DecisionRequest` into one
:class:`~btengine.decision.models.DecisionOutcome`. This is the seam a
future Rule-based Decision Engine, AI Decision Engine, or Ensemble
Decision Model (see ``docs/DECISION_ENGINE_FRAMEWORK.md`` §Future
Extension Points) plugs into via dependency injection —
:class:`~btengine.decision.engine.DecisionEngine`'s constructor accepts
any list of `DecisionProvider` instances.

Unlike :mod:`btengine.signal_validation.checks`, this module ships
**zero concrete implementations**. A named, generic analyzer (funding,
open interest, ...) exists for every
:mod:`btengine.scoring.providers` stub because the four analyzers are a
fixed, known set; there is no equivalent fixed set of "decision
providers" today — "Rule-based," "AI," and "Ensemble" are all future,
strategy-owner-defined content, not generic infrastructure this
framework can demonstrate with a placeholder class. "Configurable rule
execution" is satisfied by this interface being pluggable and by
:class:`~btengine.decision.config.DecisionEngineConfig.provider_priorities`
controlling evaluation order — not by a second, redundant "rule"
interface layered on top of this one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.decision.context import DecisionRequest
from btengine.decision.models import DecisionOutcome


class DecisionProvider(ABC):
    """Turns one prepared :class:`~btengine.decision.context.DecisionRequest`
    into one :class:`~btengine.decision.models.DecisionOutcome`.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """A stable, unique name for this provider.

        Used as the key
        :class:`~btengine.decision.config.DecisionEngineConfig.provider_priorities`/
        ``required_providers`` look this provider up under.
        """

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Identifies which revision of this provider's (not-yet-written)
        decision logic produced a given :class:`~btengine.decision.models.DecisionOutcome`
        — the same versioning discipline used throughout this project's
        engines.
        """

    @abstractmethod
    def decide(self, request: DecisionRequest) -> DecisionOutcome:
        """Compute this provider's :class:`~btengine.decision.models.DecisionOutcome` for ``request``."""
