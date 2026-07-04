"""Confirms the ATR/CVD/MarketStructure analyzer shells are wired
correctly (import, construct, satisfy the FeatureAnalyzer contract) — not
that they compute anything, since their calculations are not implemented.
"""

from btengine.features.atr import ATRAnalyzer
from btengine.features.base import FeatureAnalyzer
from btengine.features.cvd import CVDAnalyzer
from btengine.features.market_structure import MarketStructureAnalyzer

import pytest


def test_market_structure_analyzer_is_a_feature_analyzer() -> None:
    analyzer = MarketStructureAnalyzer()
    assert isinstance(analyzer, FeatureAnalyzer)
    assert analyzer.feature_name == "market_structure"
    with pytest.raises(NotImplementedError):
        analyzer.compute("BTCUSDT", history=None)


def test_atr_analyzer_default_period() -> None:
    analyzer = ATRAnalyzer()
    assert analyzer.period == 14
    assert analyzer.feature_name == "atr_14"
    with pytest.raises(NotImplementedError):
        analyzer.compute("BTCUSDT", history=None)


def test_atr_analyzer_custom_period() -> None:
    analyzer = ATRAnalyzer(period=21)
    assert analyzer.feature_name == "atr_21"


def test_atr_analyzer_rejects_nonpositive_period() -> None:
    with pytest.raises(ValueError):
        ATRAnalyzer(period=0)


def test_cvd_analyzer_is_a_feature_analyzer() -> None:
    analyzer = CVDAnalyzer()
    assert isinstance(analyzer, FeatureAnalyzer)
    assert analyzer.feature_name == "cvd"
    with pytest.raises(NotImplementedError):
        analyzer.compute("BTCUSDT", history=None)
