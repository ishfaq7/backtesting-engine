import pytest
from pydantic import ValidationError

from btengine.strategy.rules.risk_management import RiskManagementRules


def test_defaults_are_all_unset() -> None:
    rules = RiskManagementRules()
    assert rules.enabled is False
    assert rules.max_risk_per_trade_pct is None
    assert rules.max_leverage is None
    assert rules.max_concurrent_positions is None
    assert rules.max_daily_loss_pct is None
    assert rules.stop_loss_type is None


def test_valid_values_are_accepted() -> None:
    rules = RiskManagementRules(
        enabled=True, max_risk_per_trade_pct=1.0, max_leverage=5.0,
        max_concurrent_positions=2, max_daily_loss_pct=3.0, stop_loss_type="FIXED_PCT",
    )
    assert rules.max_leverage == 5.0


@pytest.mark.parametrize(
    "field, value",
    [
        ("max_risk_per_trade_pct", 0),
        ("max_risk_per_trade_pct", -1),
        ("max_leverage", 0),
        ("max_concurrent_positions", 0),
        ("max_daily_loss_pct", -0.5),
    ],
)
def test_rejects_nonpositive_values_when_set(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        RiskManagementRules(**{field: value})


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RiskManagementRules(unexpected_field=1)  # type: ignore[call-arg]
