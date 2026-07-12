from datetime import datetime, timezone

import pytest

from btengine.features.base import FeatureAnalyzer, FeatureValue


def test_feature_analyzer_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        FeatureAnalyzer()  # type: ignore[abstract]


def test_concrete_analyzer_must_implement_both_members() -> None:
    class Incomplete(FeatureAnalyzer):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_concrete_analyzer_works_when_fully_implemented() -> None:
    class Constant(FeatureAnalyzer):
        @property
        def feature_name(self) -> str:
            return "constant"

        def compute(self, symbol, history):  # type: ignore[override]
            return FeatureValue(
                symbol=symbol, feature_name=self.feature_name,
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), value=1.0,
            )

    analyzer = Constant()
    result = analyzer.compute("BTCUSDT", history=None)
    assert result.value == 1.0
    assert result.feature_name == "constant"


def test_feature_value_is_frozen() -> None:
    value = FeatureValue(
        symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), value=1.0
    )
    with pytest.raises(Exception):
        value.value = 2.0  # type: ignore[misc]


def test_feature_value_defaults_to_version_v1() -> None:
    value = FeatureValue(
        symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), value=1.0
    )
    assert value.version == "v1"


def test_feature_value_accepts_explicit_version() -> None:
    value = FeatureValue(
        symbol="BTCUSDT", feature_name="x", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), value=1.0,
        version="v2",
    )
    assert value.version == "v2"
