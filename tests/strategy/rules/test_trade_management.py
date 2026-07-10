import pytest
from pydantic import ValidationError

from btengine.strategy.rules.primitives import ComparisonOperator, RuleCondition
from btengine.strategy.rules.trade_management import TradeManagementAction, TradeManagementRules


def test_defaults_are_disabled_with_no_actions() -> None:
    rules = TradeManagementRules()
    assert rules.enabled is False
    assert rules.actions == []


def test_action_requires_a_trigger_condition() -> None:
    with pytest.raises(ValidationError):
        TradeManagementAction(name="a1")  # type: ignore[call-arg]


def test_action_defaults_action_and_params_unset() -> None:
    action = TradeManagementAction(
        name="a1", trigger=RuleCondition(name="t1", operator=ComparisonOperator.GT)
    )
    assert action.action is None
    assert action.action_params == {}
    assert action.enabled is True


def test_ruleset_can_hold_multiple_actions() -> None:
    rules = TradeManagementRules(
        enabled=True,
        actions=[
            TradeManagementAction(
                name="a1", trigger=RuleCondition(name="t1", feature="x", operator=ComparisonOperator.GT, value=1),
                action="MOVE_STOP_TO_BREAKEVEN",
            ),
            TradeManagementAction(
                name="a2", trigger=RuleCondition(name="t2", feature="y", operator=ComparisonOperator.LT, value=2),
                action="PARTIAL_EXIT", action_params={"fraction": 0.5},
            ),
        ],
    )
    assert len(rules.actions) == 2
    assert rules.actions[1].action_params["fraction"] == 0.5


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TradeManagementRules(unexpected_field=1)  # type: ignore[call-arg]
