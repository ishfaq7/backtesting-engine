import pytest

from btengine.features.pipeline.market_structure import MarketStructureFeatures


def test_module_name_is_market_structure() -> None:
    assert MarketStructureFeatures().module_name == "market_structure"


def test_compute_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        MarketStructureFeatures().compute("BTCUSDT", [])
