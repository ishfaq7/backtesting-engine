import pytest

from btengine.decision.checks.base import DecisionValidationCheck


def test_decision_validation_check_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        DecisionValidationCheck()  # type: ignore[abstract]
