from datetime import datetime, timezone

import pytest

from btengine.backtest.performance_tracker import PerformanceTracker
from btengine.backtest.position_manager import ClosedTrade

UTC = timezone.utc


def _trade(pnl: float) -> ClosedTrade:
    return ClosedTrade(
        symbol="BTCUSDT", side="LONG", quantity=1, entry_price=100, exit_price=100 + pnl,
        exit_time=datetime(2024, 1, 1, tzinfo=UTC), realized_pnl=pnl, fee=0.0,
    )


def test_summary_with_no_activity_returns_initial_cash() -> None:
    tracker = PerformanceTracker(initial_cash=10_000)
    summary = tracker.summary([])
    assert summary.final_equity == 10_000
    assert summary.total_return == 0.0
    assert summary.max_drawdown == 0.0
    assert summary.num_trades == 0
    assert summary.win_rate is None
    assert summary.profit_factor is None


def test_summary_computes_total_return() -> None:
    tracker = PerformanceTracker(initial_cash=10_000)
    tracker.record_snapshot(datetime(2024, 1, 1, tzinfo=UTC), 10_000)
    tracker.record_snapshot(datetime(2024, 1, 2, tzinfo=UTC), 11_000)
    summary = tracker.summary([])
    assert summary.total_return == pytest.approx(0.1)
    assert summary.final_equity == 11_000


def test_max_drawdown_tracks_peak_to_trough() -> None:
    tracker = PerformanceTracker(initial_cash=100)
    for value in (100, 150, 90, 120):
        tracker.record_snapshot(datetime(2024, 1, 1, tzinfo=UTC), value)
    # peak 150 -> trough 90 => drawdown of 40%
    assert tracker.max_drawdown() == pytest.approx(0.4)


def test_win_rate_and_profit_factor_with_mixed_trades() -> None:
    tracker = PerformanceTracker(initial_cash=1000)
    trades = [_trade(10), _trade(-5), _trade(20)]
    summary = tracker.summary(trades)
    assert summary.num_trades == 3
    assert summary.win_rate == pytest.approx(2 / 3)
    assert summary.profit_factor == pytest.approx(30 / 5)


def test_profit_factor_is_infinite_with_no_losses() -> None:
    tracker = PerformanceTracker(initial_cash=1000)
    summary = tracker.summary([_trade(10), _trade(5)])
    assert summary.profit_factor == float("inf")


def test_profit_factor_is_none_with_no_trades() -> None:
    tracker = PerformanceTracker(initial_cash=1000)
    summary = tracker.summary([])
    assert summary.profit_factor is None


def test_equity_curve_returns_a_copy() -> None:
    tracker = PerformanceTracker(initial_cash=1000)
    tracker.record_snapshot(datetime(2024, 1, 1, tzinfo=UTC), 1000)
    curve = tracker.equity_curve
    curve.append((datetime(2024, 1, 2, tzinfo=UTC), 2000))
    assert len(tracker.equity_curve) == 1
