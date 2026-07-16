"""The No Trade Validation Check contract.

Structurally the same shape as every prior engine's own check interface,
defined fresh for this package — the "each validation layer owns its
own issue/check vocabulary" convention used throughout this project.
Checks validate the *inputs* to a no-trade evaluation and the *filter
registration itself* (duplicates, conflicts with the enabled-filter
list); they never evaluate a gating *rule* — that's a
:class:`~btengine.no_trade.filters.base.NoTradeFilter`'s job, and none
of those are implemented in this framework.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.models import NoTradeValidationIssue


class NoTradeValidationCheck(ABC):
    """One independent, stateless check contributing issues to an evaluation run."""

    @property
    @abstractmethod
    def check_name(self) -> str:
        """A stable, unique name for this check (used for logging/introspection)."""

    @abstractmethod
    def run(
        self, request: NoTradeRequest, registered_filter_names: tuple[str, ...]
    ) -> list[NoTradeValidationIssue]:
        """Return every issue this check finds (empty if none).

        ``registered_filter_names`` is the as-registered (not deduplicated)
        name list, so registration problems — duplicates, conflicts with
        ``enabled_filters`` — are checkable here.
        """
