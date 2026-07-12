import math
from datetime import datetime, timezone

import pandas as pd
import pytest

from btengine.features.pipeline.base import BaseFeatureModule, _to_py_datetime, frame_to_feature_values

UTC = timezone.utc


def test_base_feature_module_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        BaseFeatureModule()  # type: ignore[abstract]


def test_concrete_module_requires_module_name() -> None:
    class Incomplete(BaseFeatureModule):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_concrete_module_works_when_implemented() -> None:
    class Named(BaseFeatureModule):
        @property
        def module_name(self) -> str:
            return "named"

    assert Named().module_name == "named"


def test_frame_to_feature_values_happy_path() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, h, tzinfo=UTC) for h in range(3)],
            "x": [1.0, 2.0, 3.0],
        }
    )
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"])
    assert len(features) == 3
    assert features[0].feature_name == "mod.x"
    assert features[0].symbol == "BTCUSDT"
    assert features[0].version == "v1"
    assert [f.value for f in features] == [1.0, 2.0, 3.0]


def test_frame_to_feature_values_skips_nan() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, h, tzinfo=UTC) for h in range(3)],
            "x": [1.0, float("nan"), 3.0],
        }
    )
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"])
    assert [f.value for f in features] == [1.0, 3.0]


def test_frame_to_feature_values_skips_inf() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, h, tzinfo=UTC) for h in range(3)],
            "x": [1.0, float("inf"), float("-inf")],
        }
    )
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"])
    assert [f.value for f in features] == [1.0]


def test_frame_to_feature_values_skips_none() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, h, tzinfo=UTC) for h in range(2)],
            "x": pd.Series([1.0, None], dtype="object"),
        }
    )
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"])
    assert len(features) == 1


def test_frame_to_feature_values_handles_multiple_columns() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": [datetime(2024, 1, 1, tzinfo=UTC)],
            "x": [1.0],
            "y": [2.0],
        }
    )
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x", "y"])
    names = {f.feature_name for f in features}
    assert names == {"mod.x", "mod.y"}


def test_frame_to_feature_values_accepts_custom_version() -> None:
    frame = pd.DataFrame({"timestamp": [datetime(2024, 1, 1, tzinfo=UTC)], "x": [1.0]})
    features = frame_to_feature_values(
        frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"], version="v2"
    )
    assert features[0].version == "v2"


def test_frame_to_feature_values_converts_pandas_timestamp_to_python_datetime() -> None:
    frame = pd.DataFrame({"timestamp": pd.to_datetime(["2024-01-01T00:00:00Z"]), "x": [1.0]})
    features = frame_to_feature_values(frame, symbol="BTCUSDT", module_name="mod", feature_columns=["x"])
    assert isinstance(features[0].timestamp, datetime)
    assert not isinstance(features[0].timestamp, pd.Timestamp)


def test_to_py_datetime_passes_through_a_plain_datetime_unchanged() -> None:
    plain = datetime(2024, 1, 1, tzinfo=UTC)
    assert _to_py_datetime(plain) is plain
