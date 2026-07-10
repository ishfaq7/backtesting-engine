import pytest
from pydantic import ValidationError

from btengine.strategy.rules.position_management import PositionManagementRules


def test_defaults_are_all_unset() -> None:
    rules = PositionManagementRules()
    assert rules.enabled is False
    assert rules.allow_pyramiding is None
    assert rules.max_position_scale_ins is None
    assert rules.netting_mode is None


def test_valid_values_are_accepted() -> None:
    rules = PositionManagementRules(enabled=True, allow_pyramiding=True, max_position_scale_ins=3, netting_mode="NET")
    assert rules.max_position_scale_ins == 3


def test_rejects_nonpositive_max_position_scale_ins() -> None:
    with pytest.raises(ValidationError):
        PositionManagementRules(max_position_scale_ins=0)


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PositionManagementRules(unexpected_field=1)  # type: ignore[call-arg]
