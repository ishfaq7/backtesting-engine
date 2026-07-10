"""Every condition-based rule category is a thin RuleSet subclass with
identical behavior — this file tests that shape once, parametrized, rather
than duplicating the same assertions across 12 near-identical files.
"""

import pytest

from btengine.strategy.rules.atr import ATRRules
from btengine.strategy.rules.cvd import CVDRules
from btengine.strategy.rules.entry import EntryRules
from btengine.strategy.rules.exit import ExitRules
from btengine.strategy.rules.funding_rate import FundingRateRules
from btengine.strategy.rules.liquidity import LiquidityRules
from btengine.strategy.rules.market_condition_filters import MarketConditionFilterRules
from btengine.strategy.rules.market_structure import MarketStructureRules
from btengine.strategy.rules.no_trade import NoTradeConditionRules
from btengine.strategy.rules.open_interest import OpenInterestRules
from btengine.strategy.rules.premium_discount import PremiumDiscountRules
from btengine.strategy.rules.primitives import ComparisonOperator, RuleCondition, RuleSet
from btengine.strategy.rules.session_filters import SessionFilterRules

ALL_CONDITION_BASED_CATEGORIES = [
    FundingRateRules,
    OpenInterestRules,
    PremiumDiscountRules,
    LiquidityRules,
    MarketStructureRules,
    CVDRules,
    ATRRules,
    EntryRules,
    ExitRules,
    NoTradeConditionRules,
    SessionFilterRules,
    MarketConditionFilterRules,
]


@pytest.mark.parametrize("category_cls", ALL_CONDITION_BASED_CATEGORIES)
def test_category_is_a_ruleset_subclass(category_cls: type) -> None:
    assert issubclass(category_cls, RuleSet)


@pytest.mark.parametrize("category_cls", ALL_CONDITION_BASED_CATEGORIES)
def test_category_defaults_to_disabled_and_empty(category_cls: type) -> None:
    instance = category_cls()
    assert instance.enabled is False
    assert instance.conditions == []


@pytest.mark.parametrize("category_cls", ALL_CONDITION_BASED_CATEGORIES)
def test_category_can_hold_conditions(category_cls: type) -> None:
    instance = category_cls(
        enabled=True,
        conditions=[RuleCondition(name="c1", feature="x", operator=ComparisonOperator.GT, value=1)],
    )
    assert len(instance.conditions) == 1
