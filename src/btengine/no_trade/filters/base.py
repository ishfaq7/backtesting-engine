"""The No Trade Filter contract: "support multiple independent filters."

Each filter answers exactly one gating question ("does the market
condition permit trading?", "does the session permit trading?") for one
:class:`~btengine.no_trade.context.NoTradeRequest`, returning one
:class:`~btengine.no_trade.models.FilterResult` — never another
filter's concern, never the aggregate verdict (that's
:class:`~btengine.no_trade.engine.NoTradeEngine`'s job). Independent
filters are what let each be implemented, versioned, tested, enabled/
disabled (via :attr:`~btengine.no_trade.config.NoTradeEngineConfig.enabled_filters`),
and replaced separately via dependency injection.

Every concrete filter in :mod:`btengine.no_trade.filters.builtin`
raises ``NotImplementedError`` from :meth:`evaluate` — what condition
should actually block trading is the strategy owner's proprietary
content, which this framework must not invent. The engine converts
that into ``FilterVerdict.CANNOT_EVALUATE``, which per the fail-safe
gating semantics can never open the gate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from btengine.no_trade.context import NoTradeRequest
from btengine.no_trade.models import FilterResult


class NoTradeFilter(ABC):
    """Answers one independent "may the system trade?" question."""

    @property
    @abstractmethod
    def filter_name(self) -> str:
        """A stable, unique name for this filter (e.g. ``"session_filter"``).

        Used as the key :attr:`~btengine.no_trade.config.NoTradeEngineConfig.enabled_filters`
        and ``filter_parameters`` look this filter up under, and checked
        for uniqueness by the "duplicate filters" validation.
        """

    @property
    @abstractmethod
    def filter_version(self) -> str:
        """Identifies which revision of this filter's (not-yet-written)
        rule produced a given result — the same versioning discipline
        used throughout this project's engines.
        """

    @abstractmethod
    def evaluate(self, request: NoTradeRequest) -> FilterResult:
        """Evaluate this filter's gating question for ``request``."""
