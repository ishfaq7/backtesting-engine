from datetime import datetime, timezone

from btengine.decision.models import DecisionContext, DecisionStatus
from btengine.risk.models import (
    ExposureStatus,
    MarketDataSnapshot,
    PortfolioStateSnapshot,
    RiskAssessment,
)
from btengine.scoring.models import StrategyScore, ValidationStatus

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def make_strategy_score(score_version: str = "v1", symbol: str = "BTCUSDT") -> StrategyScore:
    return StrategyScore(
        symbol=symbol, as_of=NOW, score_version=score_version, funding_score=None, oi_score=None,
        premium_discount_score=None, liquidity_score=None, total_score=None, confidence=1.0,
        feature_status={},
    )


def make_decision_context(strategy_version: str = "v1") -> DecisionContext:
    return DecisionContext(
        symbol="BTCUSDT", as_of=NOW, strategy_version=strategy_version, timestamp=NOW,
        decision_status=DecisionStatus.PENDING, decision_reason="pending",
        validation_status=ValidationStatus.VALID, execution_ready=False,
    )


def make_risk_assessment(strategy_version: str = "v1") -> RiskAssessment:
    return RiskAssessment(
        symbol="BTCUSDT", as_of=NOW, strategy_version=strategy_version, timestamp=NOW,
        risk_approved=False, position_size=None, leverage_allowed=None, max_risk_allowed=None,
        exposure_status=ExposureStatus.UNKNOWN, portfolio_risk=None,
        validation_status=ValidationStatus.VALID,
    )


def make_market_data(price: float = 100.0) -> MarketDataSnapshot:
    return MarketDataSnapshot(symbol="BTCUSDT", price=price, timestamp=NOW)


def make_portfolio(equity: float = 10_000.0) -> PortfolioStateSnapshot:
    return PortfolioStateSnapshot(cash=equity, equity=equity)
