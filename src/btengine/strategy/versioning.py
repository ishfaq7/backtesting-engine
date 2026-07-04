"""Strategy version metadata and an in-memory registry.

Independent from the entry-point plugin *discovery* mechanism described in
``docs/STRATEGY_AND_DATA_LAYER.md`` (which finds installed packages by
name): this only records version metadata so a research result — a
backtest, a walk-forward run, a Monte Carlo validation — can always be
traced back to exactly which named, versioned strategy implementation
produced it. Contains no strategy logic of any kind, only bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyVersion:
    """Identifies one specific version of one named strategy plugin."""

    name: str
    version: str
    description: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.name}@{self.version}"


class StrategyRegistry:
    """Tracks every known :class:`StrategyVersion` for every strategy name."""

    def __init__(self) -> None:
        self._versions: dict[str, dict[str, StrategyVersion]] = {}

    def register(self, version: StrategyVersion) -> None:
        by_version = self._versions.setdefault(version.name, {})
        by_version[version.version] = version

    def get(self, name: str, version: str) -> StrategyVersion | None:
        return self._versions.get(name, {}).get(version)

    def list_versions(self, name: str) -> list[StrategyVersion]:
        return list(self._versions.get(name, {}).values())

    def list_names(self) -> list[str]:
        return list(self._versions)
