import pytest

from btengine.decision.providers.base import DecisionProvider


def test_decision_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        DecisionProvider()  # type: ignore[abstract]
