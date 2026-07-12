import pytest

from btengine.scoring.aggregation import ScoreAggregator, WeightedSumAggregator
from btengine.scoring.config import ScoreWeights
from btengine.scoring.models import ScoreComponent


def _component(value: float | None, provider_name: str = "funding") -> ScoreComponent:
    return ScoreComponent(
        provider_name=provider_name, provider_version="v1", value=value, weight=None, confidence=1.0
    )


def test_score_aggregator_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ScoreAggregator()  # type: ignore[abstract]


def test_aggregate_returns_none_for_empty_components() -> None:
    result = WeightedSumAggregator().aggregate({}, ScoreWeights())
    assert result is None


def test_aggregate_ignores_none_components() -> None:
    components = {"funding": None, "liquidity": _component(0.8)}
    weights = ScoreWeights(liquidity=1.0)
    result = WeightedSumAggregator().aggregate(components, weights)
    assert result == 0.8


def test_aggregate_returns_none_when_a_component_has_no_weight() -> None:
    components = {"funding": _component(0.5)}
    result = WeightedSumAggregator().aggregate(components, ScoreWeights())
    assert result is None


def test_aggregate_returns_none_when_a_component_has_no_value() -> None:
    components = {"funding": _component(None)}
    weights = ScoreWeights(funding=1.0)
    result = WeightedSumAggregator().aggregate(components, weights)
    assert result is None


def test_aggregate_computes_weighted_average() -> None:
    components = {
        "funding": _component(0.8, "funding"),
        "liquidity": _component(0.2, "liquidity"),
    }
    weights = ScoreWeights(funding=3.0, liquidity=1.0)
    result = WeightedSumAggregator().aggregate(components, weights)
    expected = (0.8 * 3.0 + 0.2 * 1.0) / (3.0 + 1.0)
    assert result == pytest.approx(expected)


def test_aggregate_returns_none_when_all_weights_are_zero() -> None:
    components = {"funding": _component(0.5, "funding")}
    weights = ScoreWeights(funding=0.0)
    result = WeightedSumAggregator().aggregate(components, weights)
    assert result is None


def test_aggregate_returns_none_if_any_present_component_lacks_a_weight() -> None:
    components = {
        "funding": _component(0.5, "funding"),
        "liquidity": _component(0.5, "liquidity"),
    }
    weights = ScoreWeights(funding=1.0)  # liquidity weight missing
    result = WeightedSumAggregator().aggregate(components, weights)
    assert result is None
