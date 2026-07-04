import pytest

from btengine.feature_store.base import FeatureStore


def test_feature_store_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        FeatureStore()  # type: ignore[abstract]
