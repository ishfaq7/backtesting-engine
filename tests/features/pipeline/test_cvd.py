import pytest

from btengine.features.pipeline.cvd import CvdFeatures


def test_module_name_is_cvd() -> None:
    assert CvdFeatures().module_name == "cvd"


def test_compute_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        CvdFeatures().compute("BTCUSDT", [])
