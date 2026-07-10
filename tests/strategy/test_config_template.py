"""Confirms the shipped config/strategy/ template loads cleanly and
validates as intended: everything is disabled/placeholder except the two
genuinely-required top-level fields, so the template's own validation
output is a live demonstration of the framework working as designed.
"""

from pathlib import Path

from btengine.strategy.spec_loader import load_strategy_spec
from btengine.strategy.spec_validation import StrategySpecValidator

_CONFIG_ROOT = Path(__file__).resolve().parents[2] / "config" / "strategy"


def test_template_loads_without_error() -> None:
    spec = load_strategy_spec(_CONFIG_ROOT)
    assert spec.name == ""
    assert spec.version == ""


def test_template_every_rule_category_is_disabled() -> None:
    spec = load_strategy_spec(_CONFIG_ROOT)
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
    assert spec.scoring.enabled is False


def test_template_validation_flags_only_name_and_version() -> None:
    spec = load_strategy_spec(_CONFIG_ROOT)
    issues = StrategySpecValidator().validate(spec)
    messages = sorted(i.message for i in issues)
    assert messages == ["name is required", "version is required"]
