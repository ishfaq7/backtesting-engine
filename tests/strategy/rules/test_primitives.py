import pytest
from pydantic import ValidationError

from btengine.strategy.rules.primitives import (
    ComparisonOperator,
    RuleCombinationLogic,
    RuleCondition,
    RuleSet,
)


def test_condition_defaults_are_incomplete_placeholders() -> None:
    condition = RuleCondition(name="c1", operator=ComparisonOperator.GT)
    assert condition.feature == ""
    assert condition.value is None
    assert condition.enabled is True


def test_between_condition_requires_value_high_greater_than_value() -> None:
    with pytest.raises(ValidationError):
        RuleCondition(name="c1", operator=ComparisonOperator.BETWEEN, value=10, value_high=5)


def test_between_condition_accepts_valid_bounds() -> None:
    condition = RuleCondition(name="c1", operator=ComparisonOperator.BETWEEN, value=5, value_high=10)
    assert condition.value_high == 10


def test_between_condition_allows_unset_bounds_as_a_todo_placeholder() -> None:
    condition = RuleCondition(name="c1", operator=ComparisonOperator.BETWEEN)
    assert condition.value is None
    assert condition.value_high is None


def test_non_between_condition_rejects_value_high() -> None:
    with pytest.raises(ValidationError):
        RuleCondition(name="c1", operator=ComparisonOperator.GT, value=10, value_high=20)


def test_condition_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        RuleCondition(name="c1", operator=ComparisonOperator.GT, unexpected_field=1)  # type: ignore[call-arg]


def test_ruleset_defaults_to_disabled_with_no_conditions() -> None:
    ruleset = RuleSet()
    assert ruleset.enabled is False
    assert ruleset.conditions == []
    assert ruleset.combination_logic == RuleCombinationLogic.ALL


def test_ruleset_can_hold_multiple_conditions() -> None:
    ruleset = RuleSet(
        enabled=True,
        combination_logic=RuleCombinationLogic.ANY,
        conditions=[
            RuleCondition(name="c1", operator=ComparisonOperator.GT, feature="x", value=1),
            RuleCondition(name="c2", operator=ComparisonOperator.LT, feature="y", value=2),
        ],
    )
    assert len(ruleset.conditions) == 2
    assert ruleset.combination_logic == RuleCombinationLogic.ANY
