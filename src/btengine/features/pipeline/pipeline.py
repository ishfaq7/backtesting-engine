"""Feature Engineering Pipeline orchestrator.

Runs a configured set of independent :class:`BaseFeatureModule` instances
over their respective input series for one symbol, collects every
computed feature into a single flat list, validates the result, and
optionally persists it to a :class:`~btengine.feature_store.base.FeatureStore`
so Backtesting, Demo Trading, and Live Trading can all reuse the same
computed features instead of recomputing them.

This orchestrator has no knowledge of what any module computes or why —
it only wires "module name" to "its input records" and fans the results
out. It never generates trading signals or scores; it only produces and
stores named :class:`~btengine.features.base.FeatureValue` objects.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from btengine.feature_store.base import FeatureStore
from btengine.features.base import FeatureValue
from btengine.features.pipeline.base import BaseFeatureModule
from btengine.features.pipeline.validation import FeaturePipelineValidator, FeatureValidationIssue


@dataclass(frozen=True)
class FeaturePipelineResult:
    """The outcome of one :meth:`FeaturePipeline.run` call for one symbol."""

    symbol: str
    features: list[FeatureValue] = field(default_factory=list)
    issues: list[FeatureValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """``True`` when no ``ERROR``-severity issue was found."""
        return not any(issue.severity == "ERROR" for issue in self.issues)


class FeaturePipeline:
    """Runs a fixed set of feature modules and collects/validates their output."""

    def __init__(
        self, modules: Sequence[BaseFeatureModule], *, feature_store: FeatureStore | None = None
    ) -> None:
        self._modules = list(modules)
        self._feature_store = feature_store

    def run(
        self, symbol: str, inputs: Mapping[str, Sequence[Any]], *, persist: bool = True
    ) -> FeaturePipelineResult:
        """Compute every configured module's features for ``symbol``.

        ``inputs`` maps a module's :attr:`~BaseFeatureModule.module_name`
        to the chronological record series it should be run on. A module
        whose name is absent from ``inputs`` is skipped. When ``persist``
        is true and a ``feature_store`` was configured, the computed
        features are written to it before being returned.
        """
        features: list[FeatureValue] = []
        for module in self._modules:
            records = inputs.get(module.module_name)
            if records is None:
                continue
            features.extend(module.compute(symbol, records))

        issues = FeaturePipelineValidator().validate(features)

        if persist and self._feature_store is not None and features:
            self._feature_store.write(features)

        return FeaturePipelineResult(symbol=symbol, features=features, issues=issues)
