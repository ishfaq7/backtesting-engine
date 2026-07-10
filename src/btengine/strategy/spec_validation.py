"""Validates a :class:`~btengine.strategy.spec.StrategySpec` for
completeness and internal consistency.

Deliberately checks only structure: missing values, duplicate names, and
mathematically-contradictory numeric bounds (pure interval arithmetic on
the conditions' own stated operators/values). It never judges whether a
threshold is *reasonable*, whether a rule is *good*, or infers a value
that wasn't supplied — that is the strategy owner's call, not this
framework's. A disabled rule set is never flagged as "missing": disabling
a category is a deliberate choice, not an incomplete one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from btengine.strategy.rules.position_management import PositionManagementRules
from btengine.strategy.rules.primitives import ComparisonOperator, RuleCombinationLogic, RuleCondition, RuleSet
from btengine.strategy.rules.risk_management import RiskManagementRules
from btengine.strategy.rules.trade_management import TradeManagementRules
from btengine.strategy.scoring.config import ScoringModelConfig
from btengine.strategy.spec import StrategySpec

Severity = Literal["ERROR", "WARNING"]

_RULE_SET_FIELDS: list[str] = [
    "funding_rate_rules",
    "open_interest_rules",
    "premium_discount_rules",
    "liquidity_rules",
    "market_structure_rules",
    "cvd_rules",
    "atr_rules",
    "entry_rules",
    "exit_rules",
    "no_trade_conditions",
    "session_filters",
    "market_condition_filters",
]

KNOWN_RULE_CATEGORIES: frozenset[str] = frozenset(
    {
        "funding_rate",
        "open_interest",
        "premium_discount",
        "liquidity",
        "market_structure",
        "cvd",
        "atr",
        "entry",
        "exit",
        "risk_management",
        "no_trade",
        "trade_management",
        "position_management",
        "session_filters",
        "market_condition_filters",
    }
)


@dataclass(frozen=True)
class SpecValidationIssue:
    severity: Severity
    section: str
    message: str


class StrategySpecValidator:
    """Runs every completeness/consistency check and returns the full list
    of issues found (empty if the spec is complete and internally
    consistent).
    """

    def validate(self, spec: StrategySpec) -> list[SpecValidationIssue]:
        issues: list[SpecValidationIssue] = []
        issues += self._check_top_level_metadata(spec)
        for field_name in _RULE_SET_FIELDS:
            issues += self._check_ruleset(field_name, getattr(spec, field_name))
        issues += self._check_risk_management(spec.risk_management_rules)
        issues += self._check_position_management(spec.position_management_rules)
        issues += self._check_trade_management(spec.trade_management_rules)
        issues += self._check_scoring(spec.scoring)
        return issues

    # --- top-level ---------------------------------------------------------

    def _check_top_level_metadata(self, spec: StrategySpec) -> list[SpecValidationIssue]:
        issues: list[SpecValidationIssue] = []
        if not spec.name.strip():
            issues.append(SpecValidationIssue("ERROR", "strategy", "name is required"))
        if not spec.version.strip():
            issues.append(SpecValidationIssue("ERROR", "strategy", "version is required"))
        return issues

    # --- condition-based rule sets ------------------------------------------

    def _check_ruleset(self, section: str, ruleset: RuleSet) -> list[SpecValidationIssue]:
        if not ruleset.enabled:
            return []  # a disabled ruleset is a deliberate choice, not missing

        if not ruleset.conditions:
            return [SpecValidationIssue("ERROR", section, "enabled but has no conditions defined")]

        issues = self._check_conditions_complete(section, ruleset.conditions)
        issues += self._check_duplicate_conditions(section, ruleset.conditions)
        issues += self._check_conflicting_conditions(section, ruleset)
        return issues

    def _check_conditions_complete(
        self, section: str, conditions: list[RuleCondition]
    ) -> list[SpecValidationIssue]:
        issues: list[SpecValidationIssue] = []
        for condition in conditions:
            if not condition.enabled:
                continue
            if not condition.feature.strip():
                issues.append(
                    SpecValidationIssue("ERROR", section, f"condition {condition.name!r} is missing 'feature'")
                )
            if condition.value is None:
                issues.append(
                    SpecValidationIssue("ERROR", section, f"condition {condition.name!r} is missing 'value'")
                )
            if condition.operator == ComparisonOperator.BETWEEN and condition.value_high is None:
                issues.append(
                    SpecValidationIssue(
                        "ERROR", section, f"condition {condition.name!r} is BETWEEN but missing 'value_high'"
                    )
                )
        return issues

    def _check_duplicate_conditions(
        self, section: str, conditions: list[RuleCondition]
    ) -> list[SpecValidationIssue]:
        issues: list[SpecValidationIssue] = []

        name_counts: dict[str, int] = {}
        for condition in conditions:
            name_counts[condition.name] = name_counts.get(condition.name, 0) + 1
        for name, count in sorted(name_counts.items()):
            if count > 1:
                issues.append(
                    SpecValidationIssue("ERROR", section, f"duplicate condition name {name!r} ({count} occurrences)")
                )

        signature_names: dict[tuple, list[str]] = {}
        for condition in conditions:
            signature = (condition.feature, condition.operator, condition.value, condition.value_high)
            signature_names.setdefault(signature, []).append(condition.name)
        for names in signature_names.values():
            if len(names) > 1:
                issues.append(
                    SpecValidationIssue(
                        "WARNING", section, f"conditions {sorted(names)} are functionally identical"
                    )
                )
        return issues

    def _check_conflicting_conditions(self, section: str, ruleset: RuleSet) -> list[SpecValidationIssue]:
        if ruleset.combination_logic != RuleCombinationLogic.ALL:
            return []  # only ALL requires every condition to hold simultaneously

        by_feature: dict[str, list[RuleCondition]] = {}
        for condition in ruleset.conditions:
            if not condition.enabled or condition.value is None or not condition.feature:
                continue
            by_feature.setdefault(condition.feature, []).append(condition)

        issues: list[SpecValidationIssue] = []
        for feature, conditions in sorted(by_feature.items()):
            if len(conditions) > 1:
                issues += self._check_feature_bounds(section, feature, conditions)
        return issues

    def _check_feature_bounds(
        self, section: str, feature: str, conditions: list[RuleCondition]
    ) -> list[SpecValidationIssue]:
        lower: tuple[float, bool] | None = None  # (value, inclusive)
        upper: tuple[float, bool] | None = None
        eq_values: set[float] = set()
        neq_values: set[float] = set()

        for condition in conditions:
            value = condition.value
            assert value is not None  # filtered by caller
            if condition.operator in (ComparisonOperator.GT, ComparisonOperator.GTE):
                inclusive = condition.operator == ComparisonOperator.GTE
                if lower is None or value > lower[0]:
                    lower = (value, inclusive)
            elif condition.operator in (ComparisonOperator.LT, ComparisonOperator.LTE):
                inclusive = condition.operator == ComparisonOperator.LTE
                if upper is None or value < upper[0]:
                    upper = (value, inclusive)
            elif condition.operator == ComparisonOperator.EQ:
                eq_values.add(value)
            elif condition.operator == ComparisonOperator.NEQ:
                neq_values.add(value)
            elif condition.operator == ComparisonOperator.BETWEEN and condition.value_high is not None:
                if lower is None or value > lower[0]:
                    lower = (value, True)
                if upper is None or condition.value_high < upper[0]:
                    upper = (condition.value_high, True)

        issues: list[SpecValidationIssue] = []
        if len(eq_values) > 1:
            issues.append(
                SpecValidationIssue(
                    "ERROR", section, f"feature {feature!r} has contradictory EQ values {sorted(eq_values)}"
                )
            )
        if lower is not None and upper is not None:
            lower_value, lower_inclusive = lower
            upper_value, upper_inclusive = upper
            impossible = lower_value > upper_value or (
                lower_value == upper_value and not (lower_inclusive and upper_inclusive)
            )
            if impossible:
                issues.append(
                    SpecValidationIssue(
                        "ERROR",
                        section,
                        f"feature {feature!r} has conditions that can never both hold "
                        f"(lower bound {lower_value}, upper bound {upper_value})",
                    )
                )
        for eq in eq_values:
            if lower is not None and (eq < lower[0] or (eq == lower[0] and not lower[1])):
                issues.append(
                    SpecValidationIssue("ERROR", section, f"feature {feature!r} EQ {eq} violates its own lower bound")
                )
            if upper is not None and (eq > upper[0] or (eq == upper[0] and not upper[1])):
                issues.append(
                    SpecValidationIssue("ERROR", section, f"feature {feature!r} EQ {eq} violates its own upper bound")
                )
            if eq in neq_values:
                issues.append(
                    SpecValidationIssue("ERROR", section, f"feature {feature!r} has both EQ and NEQ on {eq}")
                )
        return issues

    # --- parameter-based rule sets -------------------------------------------

    def _check_risk_management(self, risk: RiskManagementRules) -> list[SpecValidationIssue]:
        if not risk.enabled:
            return []
        issues: list[SpecValidationIssue] = []
        for field_name in (
            "max_risk_per_trade_pct",
            "max_leverage",
            "max_concurrent_positions",
            "max_daily_loss_pct",
            "stop_loss_type",
        ):
            if getattr(risk, field_name) is None:
                issues.append(
                    SpecValidationIssue("ERROR", "risk_management_rules", f"{field_name} is required when enabled")
                )
        return issues

    def _check_position_management(self, position: PositionManagementRules) -> list[SpecValidationIssue]:
        if not position.enabled:
            return []
        issues: list[SpecValidationIssue] = []
        if position.allow_pyramiding is None:
            issues.append(
                SpecValidationIssue("ERROR", "position_management_rules", "allow_pyramiding is required when enabled")
            )
        if position.netting_mode is None:
            issues.append(
                SpecValidationIssue("ERROR", "position_management_rules", "netting_mode is required when enabled")
            )
        if position.allow_pyramiding and position.max_position_scale_ins is None:
            issues.append(
                SpecValidationIssue(
                    "ERROR",
                    "position_management_rules",
                    "max_position_scale_ins is required when allow_pyramiding is True",
                )
            )
        return issues

    def _check_trade_management(self, trade_management: TradeManagementRules) -> list[SpecValidationIssue]:
        if not trade_management.enabled:
            return []
        if not trade_management.actions:
            return [SpecValidationIssue("ERROR", "trade_management_rules", "enabled but has no actions defined")]

        issues: list[SpecValidationIssue] = []
        name_counts: dict[str, int] = {}
        for action in trade_management.actions:
            name_counts[action.name] = name_counts.get(action.name, 0) + 1
            if not action.enabled:
                continue
            if action.action is None:
                issues.append(
                    SpecValidationIssue("ERROR", "trade_management_rules", f"action {action.name!r} is missing 'action'")
                )
            if not action.trigger.feature.strip():
                issues.append(
                    SpecValidationIssue(
                        "ERROR", "trade_management_rules", f"action {action.name!r} trigger is missing 'feature'"
                    )
                )
            if action.trigger.value is None:
                issues.append(
                    SpecValidationIssue(
                        "ERROR", "trade_management_rules", f"action {action.name!r} trigger is missing 'value'"
                    )
                )
        for name, count in sorted(name_counts.items()):
            if count > 1:
                issues.append(
                    SpecValidationIssue("ERROR", "trade_management_rules", f"duplicate action name {name!r}")
                )
        return issues

    # --- scoring -------------------------------------------------------------

    def _check_scoring(self, scoring: ScoringModelConfig) -> list[SpecValidationIssue]:
        if not scoring.enabled:
            return []
        issues: list[SpecValidationIssue] = []
        if not scoring.factors:
            issues.append(SpecValidationIssue("ERROR", "scoring", "enabled but has no factors defined"))
        for factor in scoring.factors:
            if not factor.enabled:
                continue
            if not factor.source_rule_set.strip():
                issues.append(
                    SpecValidationIssue("ERROR", "scoring", f"factor {factor.name!r} is missing 'source_rule_set'")
                )
            elif factor.source_rule_set not in KNOWN_RULE_CATEGORIES:
                issues.append(
                    SpecValidationIssue(
                        "ERROR",
                        "scoring",
                        f"factor {factor.name!r} references unknown source_rule_set {factor.source_rule_set!r}",
                    )
                )
            if factor.weight is None:
                issues.append(SpecValidationIssue("ERROR", "scoring", f"factor {factor.name!r} is missing 'weight'"))
        if scoring.entry_threshold is None:
            issues.append(SpecValidationIssue("ERROR", "scoring", "entry_threshold is required when enabled"))
        if scoring.exit_threshold is None:
            issues.append(SpecValidationIssue("ERROR", "scoring", "exit_threshold is required when enabled"))
        return issues
