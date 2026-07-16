from datetime import datetime, timezone

from btengine.decision.models import DecisionContext, DecisionStatus
from btengine.risk.models import MarketDataSnapshot, PortfolioStateSnapshot, PositionStateSnapshot
from btengine.scoring.models import StrategyScore, ValidationStatus

UTC = timezone.utc
NOW = datetime(2024, 1, 1, tzinfo=UTC)


def make_strategy_score(score_version: str = "v1") -> StrategyScore:
    return StrategyScore(
        symbol="BTCUSDT", as_of=NOW, score_version=score_version, funding_score=None, oi_score=None,
        premium_discount_score=None, liquidity_score=None, total_score=None, confidence=1.0,
        feature_status={},
    )


def make_decision_context(strategy_version: str = "v1") -> DecisionContext:
    return DecisionContext(
        symbol="BTCUSDT", as_of=NOW, strategy_version=strategy_version, timestamp=NOW,
        decision_status=DecisionStatus.PENDING, decision_reason="pending",
        validation_status=ValidationStatus.VALID, execution_ready=False,
    )


def make_position(
    symbol: str = "BTCUSDT", quantity: float = 1.0, avg_entry_price: float = 100.0,
    unrealized_pnl: float = 0.0, leverage: float | None = None,
) -> PositionStateSnapshot:
    return PositionStateSnapshot(
        symbol=symbol, quantity=quantity, avg_entry_price=avg_entry_price,
        unrealized_pnl=unrealized_pnl, leverage=leverage,
    )


def make_portfolio(
    cash: float = 10_000.0, equity: float = 10_000.0,
    positions: tuple[PositionStateSnapshot, ...] = (),
    daily_realized_pnl: float | None = None, peak_equity: float | None = None,
    margin_used: float | None = None,
) -> PortfolioStateSnapshot:
    return PortfolioStateSnapshot(
        cash=cash, equity=equity, positions=positions, daily_realized_pnl=daily_realized_pnl,
        peak_equity=peak_equity, margin_used=margin_used,
    )


def make_market_data(price: float = 100.0, volatility: float | None = None) -> MarketDataSnapshot:
    return MarketDataSnapshot(symbol="BTCUSDT", price=price, timestamp=NOW, volatility=volatility)
