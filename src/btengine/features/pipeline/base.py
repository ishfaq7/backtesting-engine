"""Shared contract and helpers for the Feature Engineering Pipeline.

A pipeline module is a pure function of a historical record series: given
a symbol and a chronological list of one canonical record type
(:class:`~btengine.data.schema.Candle`,
:class:`~btengine.data.schema.FundingRate`,
:class:`~btengine.data.schema.OpenInterest`,
:class:`~btengine.data.schema.Liquidation`, or
:class:`~btengine.data.schema.LongShortRatio` — all unchanged), it returns
a list of named :class:`~btengine.features.base.FeatureValue` objects. No
I/O, no knowledge of any strategy, no signals — only data transformation.

This is the batch/pipeline counterpart to the single-point-in-time
``FeatureAnalyzer`` in :mod:`btengine.features.base`, used for building
historical feature datasets (for a Feature Store, for research) rather
than answering "what's this feature's value right now" during a live
backtest tick.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import pandas as pd

from btengine.features.base import FeatureValue

FEATURE_VERSION = "v1"


class BaseFeatureModule(ABC):
    """Identifies one independent feature-computation module."""

    @property
    @abstractmethod
    def module_name(self) -> str:
        """A stable, unique name for this module.

        Used both to key its required input series in
        :meth:`~btengine.features.pipeline.pipeline.FeaturePipeline.run`
        and as the namespace prefix for every feature name it emits (e.g.
        ``"price.return_pct"``), so two modules can never collide in the
        Feature Store.
        """


def frame_to_feature_values(
    frame: pd.DataFrame,
    *,
    symbol: str,
    module_name: str,
    feature_columns: Sequence[str],
    version: str = FEATURE_VERSION,
) -> list[FeatureValue]:
    """Convert a DataFrame with a ``timestamp`` column and one column per
    feature into a flat list of :class:`FeatureValue`.

    Any cell that is ``NaN``/``None``/``inf`` (insufficient rolling-window
    history, or an undefined ratio like ``0/0``) is silently omitted
    rather than emitted as an invalid value — a feature simply doesn't
    exist yet at that timestamp, rather than existing with a bad value.
    """
    features: list[FeatureValue] = []
    for column in feature_columns:
        feature_name = f"{module_name}.{column}"
        for timestamp, value in zip(frame["timestamp"], frame[column]):
            if value is None:
                continue
            numeric_value = float(value)
            if math.isnan(numeric_value) or math.isinf(numeric_value):
                continue
            features.append(
                FeatureValue(
                    symbol=symbol,
                    feature_name=feature_name,
                    timestamp=_to_py_datetime(timestamp),
                    value=numeric_value,
                    version=version,
                )
            )
    return features


def _to_py_datetime(value: Any) -> Any:
    to_pydatetime = getattr(value, "to_pydatetime", None)
    return to_pydatetime() if callable(to_pydatetime) else value
