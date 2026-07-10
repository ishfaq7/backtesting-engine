from btengine.strategy.rules.funding_rate import FundingRateRules
from btengine.strategy.rules.no_trade import NoTradeConditionRules
from btengine.strategy.rules.position_management import PositionManagementRules
from btengine.strategy.rules.primitives import (
    ComparisonOperator,
    RuleCombinationLogic,
    RuleCondition,
)
from btengine.strategy.rules.risk_management import RiskManagementRules
from btengine.strategy.rules.trade_management import TradeManagementAction, TradeManagementRules
from btengine.strategy.scoring.config import ScoringFactorConfig, ScoringModelConfig
from btengine.strategy.spec import StrategySpec
from btengine.strategy.spec_validation import StrategySpecValidator


def _spec(**overrides) -> StrategySpec:
    base = dict(name="x", version="0.1.0", scoring=ScoringModelConfig(version="0.1.0"))
    base.update(overrides)
    return StrategySpec(**base)


def test_fully_disabled_spec_has_no_issues() -> None:
    assert StrategySpecValidator().validate(_spec()) == []


def test_blank_name_and_version_are_flagged() -> None:
    spec = _spec(name="  ", version=" ")
    issues = StrategySpecValidator().validate(spec)
    messages = [i.message for i in issues]
    assert any("name is required" in m for m in messages)
    assert any("version is required" in m for m in messages)


def test_enabled_ruleset_with_no_conditions_is_missing() -> None:
    spec = _spec(funding_rate_rules=FundingRateRules(enabled=True))
    issues = StrategySpecValidator().validate(spec)
    assert len(issues) == 1
    assert issues[0].severity == "ERROR"
    assert issues[0].section == "funding_rate_rules"
    assert "no conditions" in issues[0].message


def test_condition_missing_feature_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True, conditions=[RuleCondition(name="c1", operator=ComparisonOperator.GT, value=1)]
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("missing 'feature'" in i.message for i in issues)


def test_condition_missing_value_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT)],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("missing 'value'" in i.message for i in issues)


def test_between_condition_missing_value_high_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.BETWEEN, value=1)
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("missing 'value_high'" in i.message for i in issues)


def test_disabled_condition_is_not_flagged_for_missing_value() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, enabled=False),
                RuleCondition(name="c2", feature="y", operator=ComparisonOperator.GT, value=1),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert issues == []


def test_duplicate_condition_names_are_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=1),
                RuleCondition(name="c1", feature="y", operator=ComparisonOperator.LT, value=2),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("duplicate condition name" in i.message for i in issues)


def test_functionally_identical_conditions_are_warned_not_erred() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=1),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.GT, value=1),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert len(issues) == 1
    assert issues[0].severity == "WARNING"
    assert "functionally identical" in issues[0].message


def test_contradictory_bounds_on_same_feature_are_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=10),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("can never both hold" in i.message for i in issues)


def test_equal_bound_edge_case_gt_and_lt_same_value_is_impossible() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=5),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("can never both hold" in i.message for i in issues)


def test_gte_and_lte_same_value_is_possible() -> None:
    # x >= 5 AND x <= 5 is satisfiable (x == 5) - not a conflict.
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GTE, value=5),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LTE, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert issues == []


def test_non_conflicting_bounds_are_not_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=5),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LT, value=10),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert issues == []


def test_contradictory_eq_values_are_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.EQ, value=5),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.EQ, value=6),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("contradictory EQ values" in i.message for i in issues)


def test_eq_value_outside_bound_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.EQ, value=1),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.GT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("violates its own lower bound" in i.message for i in issues)


def test_between_condition_combined_with_other_bounds_on_same_feature() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.BETWEEN, value=1, value_high=10),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.GT, value=20),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("can never both hold" in i.message for i in issues)


def test_eq_value_above_upper_bound_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.EQ, value=10),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("violates its own upper bound" in i.message for i in issues)


def test_eq_and_neq_same_value_is_flagged() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.EQ, value=5),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.NEQ, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("both EQ and NEQ" in i.message for i in issues)


def test_any_combination_logic_skips_conflict_detection() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            combination_logic=RuleCombinationLogic.ANY,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=10),
                RuleCondition(name="c2", feature="x", operator=ComparisonOperator.LT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert issues == []


def test_different_features_are_never_compared_against_each_other() -> None:
    spec = _spec(
        funding_rate_rules=FundingRateRules(
            enabled=True,
            conditions=[
                RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=10),
                RuleCondition(name="c2", feature="y", operator=ComparisonOperator.LT, value=5),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert issues == []


def test_no_trade_conditions_use_the_same_generic_checks() -> None:
    spec = _spec(no_trade_conditions=NoTradeConditionRules(enabled=True))
    issues = StrategySpecValidator().validate(spec)
    assert len(issues) == 1
    assert issues[0].section == "no_trade_conditions"


# --- risk management ---------------------------------------------------------


def test_risk_management_enabled_requires_every_field() -> None:
    spec = _spec(risk_management_rules=RiskManagementRules(enabled=True))
    issues = StrategySpecValidator().validate(spec)
    fields_mentioned = {i.message.split(" is required")[0] for i in issues}
    assert fields_mentioned == {
        "max_risk_per_trade_pct", "max_leverage", "max_concurrent_positions",
        "max_daily_loss_pct", "stop_loss_type",
    }


def test_risk_management_complete_config_has_no_issues() -> None:
    spec = _spec(
        risk_management_rules=RiskManagementRules(
            enabled=True, max_risk_per_trade_pct=1, max_leverage=5,
            max_concurrent_positions=1, max_daily_loss_pct=3, stop_loss_type="FIXED_PCT",
        )
    )
    assert StrategySpecValidator().validate(spec) == []


# --- position management -----------------------------------------------------


def test_position_management_enabled_requires_allow_pyramiding_and_netting_mode() -> None:
    spec = _spec(position_management_rules=PositionManagementRules(enabled=True))
    issues = StrategySpecValidator().validate(spec)
    messages = [i.message for i in issues]
    assert any("allow_pyramiding is required" in m for m in messages)
    assert any("netting_mode is required" in m for m in messages)


def test_position_management_pyramiding_requires_scale_ins() -> None:
    spec = _spec(
        position_management_rules=PositionManagementRules(
            enabled=True, allow_pyramiding=True, netting_mode="NET"
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("max_position_scale_ins is required" in i.message for i in issues)


def test_position_management_no_pyramiding_does_not_require_scale_ins() -> None:
    spec = _spec(
        position_management_rules=PositionManagementRules(
            enabled=True, allow_pyramiding=False, netting_mode="NET"
        )
    )
    assert StrategySpecValidator().validate(spec) == []


# --- trade management ---------------------------------------------------------


def test_trade_management_enabled_with_no_actions_is_missing() -> None:
    spec = _spec(trade_management_rules=TradeManagementRules(enabled=True))
    issues = StrategySpecValidator().validate(spec)
    assert len(issues) == 1
    assert "no actions" in issues[0].message


def test_trade_management_action_missing_action_name_is_flagged() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", trigger=RuleCondition(name="t1", feature="x", operator=ComparisonOperator.GT, value=1)
                )
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("missing 'action'" in i.message for i in issues)


def test_trade_management_disabled_action_is_not_checked_for_completeness() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", enabled=False,
                    trigger=RuleCondition(name="t1", operator=ComparisonOperator.GT),
                )
            ],
        )
    )
    assert StrategySpecValidator().validate(spec) == []


def test_trade_management_action_trigger_missing_feature_is_flagged() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", action="X",
                    trigger=RuleCondition(name="t1", operator=ComparisonOperator.GT, value=1),
                )
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("trigger is missing 'feature'" in i.message for i in issues)


def test_trade_management_action_trigger_missing_value_is_flagged() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", action="X",
                    trigger=RuleCondition(name="t1", feature="x", operator=ComparisonOperator.GT),
                )
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("trigger is missing 'value'" in i.message for i in issues)


def test_trade_management_duplicate_action_names_flagged() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", action="X",
                    trigger=RuleCondition(name="t1", feature="x", operator=ComparisonOperator.GT, value=1),
                ),
                TradeManagementAction(
                    name="a1", action="Y",
                    trigger=RuleCondition(name="t2", feature="y", operator=ComparisonOperator.LT, value=2),
                ),
            ],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("duplicate action name" in i.message for i in issues)


def test_trade_management_complete_action_has_no_issues() -> None:
    spec = _spec(
        trade_management_rules=TradeManagementRules(
            enabled=True,
            actions=[
                TradeManagementAction(
                    name="a1", action="MOVE_STOP_TO_BREAKEVEN",
                    trigger=RuleCondition(name="t1", feature="x", operator=ComparisonOperator.GT, value=1),
                )
            ],
        )
    )
    assert StrategySpecValidator().validate(spec) == []


# --- scoring -------------------------------------------------------------------


def test_scoring_enabled_with_no_factors_is_missing() -> None:
    spec = _spec(scoring=ScoringModelConfig(version="0.1.0", enabled=True))
    issues = StrategySpecValidator().validate(spec)
    assert any("no factors" in i.message for i in issues)


def test_scoring_factor_missing_source_and_weight_is_flagged() -> None:
    spec = _spec(
        scoring=ScoringModelConfig(
            version="0.1.0", enabled=True, factors=[ScoringFactorConfig(name="f1")],
            entry_threshold=1, exit_threshold=0,
        )
    )
    issues = StrategySpecValidator().validate(spec)
    messages = [i.message for i in issues]
    assert any("missing 'source_rule_set'" in m for m in messages)
    assert any("missing 'weight'" in m for m in messages)


def test_scoring_factor_unknown_source_rule_set_is_flagged() -> None:
    spec = _spec(
        scoring=ScoringModelConfig(
            version="0.1.0", enabled=True,
            factors=[ScoringFactorConfig(name="f1", source_rule_set="not_a_real_category", weight=1.0)],
            entry_threshold=1, exit_threshold=0,
        )
    )
    issues = StrategySpecValidator().validate(spec)
    assert any("unknown source_rule_set" in i.message for i in issues)


def test_scoring_disabled_factor_is_not_checked_for_completeness() -> None:
    spec = _spec(
        scoring=ScoringModelConfig(
            version="0.1.0", enabled=True,
            factors=[ScoringFactorConfig(name="f1", enabled=False)],
            entry_threshold=1, exit_threshold=0,
        )
    )
    assert StrategySpecValidator().validate(spec) == []


def test_scoring_missing_thresholds_are_flagged() -> None:
    spec = _spec(
        scoring=ScoringModelConfig(
            version="0.1.0", enabled=True,
            factors=[ScoringFactorConfig(name="f1", source_rule_set="funding_rate", weight=1.0)],
        )
    )
    issues = StrategySpecValidator().validate(spec)
    messages = [i.message for i in issues]
    assert any("entry_threshold is required" in m for m in messages)
    assert any("exit_threshold is required" in m for m in messages)


def test_scoring_complete_config_has_no_issues() -> None:
    spec = _spec(
        scoring=ScoringModelConfig(
            version="0.1.0", enabled=True,
            factors=[ScoringFactorConfig(name="f1", source_rule_set="funding_rate", weight=1.0)],
            entry_threshold=1.0, exit_threshold=0.0,
        )
    )
    assert StrategySpecValidator().validate(spec) == []


def test_disabled_scoring_is_not_checked() -> None:
    spec = _spec(scoring=ScoringModelConfig(version="0.1.0", enabled=False))
    assert StrategySpecValidator().validate(spec) == []
