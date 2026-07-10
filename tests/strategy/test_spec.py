import pytest
from pydantic import ValidationError

from btengine.strategy.profiles import StrategyProfileName
from btengine.strategy.rules.funding_rate import FundingRateRules
from btengine.strategy.scoring.config import ScoringModelConfig
from btengine.strategy.spec import StrategySpec


def test_scoring_is_required() -> None:
    with pytest.raises(ValidationError):
        StrategySpec(name="x", version="0.1.0")  # type: ignore[call-arg]


def test_minimal_valid_spec_has_every_category_disabled_by_default() -> None:
    spec = StrategySpec(name="x", version="0.1.0", scoring=ScoringModelConfig(version="0.1.0"))
    assert spec.funding_rate_rules.enabled is False
    assert spec.open_interest_rules.enabled is False
    assert spec.premium_discount_rules.enabled is False
    assert spec.liquidity_rules.enabled is False
    assert spec.market_structure_rules.enabled is False
    assert spec.cvd_rules.enabled is False
    assert spec.atr_rules.enabled is False
    assert spec.entry_rules.enabled is False
    assert spec.exit_rules.enabled is False
    assert spec.risk_management_rules.enabled is False
    assert spec.no_trade_conditions.enabled is False
    assert spec.trade_management_rules.enabled is False
    assert spec.position_management_rules.enabled is False
    assert spec.session_filters.enabled is False
    assert spec.market_condition_filters.enabled is False
    assert spec.known_assumptions == []
    assert spec.todo == []


def test_profile_reference_is_optional() -> None:
    spec = StrategySpec(name="x", version="0.1.0", scoring=ScoringModelConfig(version="0.1.0"))
    assert spec.profile is None

    spec_with_profile = StrategySpec(
        name="x", version="0.1.0", profile=StrategyProfileName.BALANCED,
        scoring=ScoringModelConfig(version="0.1.0"),
    )
    assert spec_with_profile.profile == StrategyProfileName.BALANCED


def test_spec_can_be_constructed_with_explicit_rule_categories() -> None:
    spec = StrategySpec(
        name="x", version="0.1.0",
        scoring=ScoringModelConfig(version="0.1.0"),
        funding_rate_rules=FundingRateRules(enabled=True),
    )
    assert spec.funding_rate_rules.enabled is True


def test_known_assumptions_and_todo_are_free_text_lists() -> None:
    spec = StrategySpec(
        name="x", version="0.1.0", scoring=ScoringModelConfig(version="0.1.0"),
        known_assumptions=["Funding rate is sourced from Binance only"],
        todo=["Define entry threshold"],
    )
    assert spec.known_assumptions == ["Funding rate is sourced from Binance only"]
    assert spec.todo == ["Define entry threshold"]


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        StrategySpec(
            name="x", version="0.1.0", scoring=ScoringModelConfig(version="0.1.0"),
            unexpected_field=1,  # type: ignore[call-arg]
        )
