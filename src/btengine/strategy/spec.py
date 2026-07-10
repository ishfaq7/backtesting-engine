"""The top-level Strategy Specification: every rule category, assembled.

A :class:`StrategySpec` is the complete, versioned, configurable
description of a strategy's rules — everything a (not-yet-built) concrete
``Strategy`` plugin implementation would read to parametrize its
analyzers, scoring, and policies. It contains no logic: every field is
either a :class:`~btengine.strategy.rules.primitives.RuleSet` (or a
parameter container, for Risk/Position Management) left for the owner to
fill in, or bookkeeping metadata (name, version, known assumptions, open
TODOs).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from btengine.strategy.profiles import StrategyProfileName
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
from btengine.strategy.rules.position_management import PositionManagementRules
from btengine.strategy.rules.premium_discount import PremiumDiscountRules
from btengine.strategy.rules.risk_management import RiskManagementRules
from btengine.strategy.rules.session_filters import SessionFilterRules
from btengine.strategy.rules.trade_management import TradeManagementRules
from btengine.strategy.scoring.config import ScoringModelConfig


class StrategySpec(BaseModel):
    """The complete, assembled configuration for one strategy."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str  # TODO(owner): required, e.g. "0.1.0" - see strategy/versioning.py for the runtime registry
    profile: StrategyProfileName | None = None  # TODO(owner): optional reference to a StrategyProfile preset

    funding_rate_rules: FundingRateRules = Field(default_factory=FundingRateRules)
    open_interest_rules: OpenInterestRules = Field(default_factory=OpenInterestRules)
    premium_discount_rules: PremiumDiscountRules = Field(default_factory=PremiumDiscountRules)
    liquidity_rules: LiquidityRules = Field(default_factory=LiquidityRules)
    market_structure_rules: MarketStructureRules = Field(default_factory=MarketStructureRules)
    cvd_rules: CVDRules = Field(default_factory=CVDRules)
    atr_rules: ATRRules = Field(default_factory=ATRRules)

    scoring: ScoringModelConfig

    entry_rules: EntryRules = Field(default_factory=EntryRules)
    exit_rules: ExitRules = Field(default_factory=ExitRules)
    risk_management_rules: RiskManagementRules = Field(default_factory=RiskManagementRules)
    no_trade_conditions: NoTradeConditionRules = Field(default_factory=NoTradeConditionRules)
    trade_management_rules: TradeManagementRules = Field(default_factory=TradeManagementRules)
    position_management_rules: PositionManagementRules = Field(default_factory=PositionManagementRules)
    session_filters: SessionFilterRules = Field(default_factory=SessionFilterRules)
    market_condition_filters: MarketConditionFilterRules = Field(default_factory=MarketConditionFilterRules)

    known_assumptions: list[str] = Field(default_factory=list)
    todo: list[str] = Field(default_factory=list)
