import pytest

from btengine.signal_validation.checks.base import ValidationCheck


def test_validation_check_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        ValidationCheck()  # type: ignore[abstract]
