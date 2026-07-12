import pytest

from btengine.features.pipeline.premium_discount import PremiumDiscountFeatures


def test_module_name_is_premium_discount() -> None:
    assert PremiumDiscountFeatures().module_name == "premium_discount"


def test_compute_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        PremiumDiscountFeatures().compute("BTCUSDT", [])
