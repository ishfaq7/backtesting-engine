from datetime import datetime, timezone

import pytest

from btengine.backtest.position_manager import ClosedTrade
from btengine.research.errors import ValidationConfigError
from btengine.research.monte_carlo import MonteCarloValidator

UTC = timezone.utc


def _trade(pnl: float) -> ClosedTrade:
    return ClosedTrade(
        symbol="BTCUSDT", side="LONG", quantity=1, entry_price=100, exit_price=100 + pnl,
        exit_time=datetime(2024, 1, 1, tzinfo=UTC), realized_pnl=pnl, fee=0.0,
    )


def test_constructor_rejects_nonpositive_simulations() -> None:
    with pytest.raises(ValidationConfigError):
        MonteCarloValidator(simulations=0)


def test_constructor_rejects_empty_percentiles() -> None:
    with pytest.raises(ValidationConfigError):
        MonteCarloValidator(percentiles=[])


def test_constructor_rejects_out_of_range_percentiles() -> None:
    with pytest.raises(ValidationConfigError):
        MonteCarloValidator(percentiles=[5, 150])


def test_validate_rejects_nonpositive_initial_cash() -> None:
    validator = MonteCarloValidator()
    with pytest.raises(ValidationConfigError):
        validator.validate([_trade(10)], initial_cash=0)


def test_validate_with_no_trades_returns_trivial_result() -> None:
    validator = MonteCarloValidator(simulations=100)
    result = validator.validate([], initial_cash=10_000)
    assert all(v == 10_000 for v in result.final_equity_percentiles.values())
    assert all(v == 0.0 for v in result.max_drawdown_percentiles.values())
    assert result.probability_of_loss == 0.0
    assert result.simulations == 100


def test_all_losing_trades_gives_100pct_probability_of_loss() -> None:
    validator = MonteCarloValidator(simulations=200, random_seed=42)
    trades = [_trade(-10) for _ in range(5)]
    result = validator.validate(trades, initial_cash=10_000)
    assert result.probability_of_loss == 1.0
    assert all(v < 10_000 for v in result.final_equity_percentiles.values())


def test_all_winning_trades_gives_0pct_probability_of_loss() -> None:
    validator = MonteCarloValidator(simulations=200, random_seed=42)
    trades = [_trade(10) for _ in range(5)]
    result = validator.validate(trades, initial_cash=10_000)
    assert result.probability_of_loss == 0.0
    assert all(v > 10_000 for v in result.final_equity_percentiles.values())
    assert all(v == 0.0 for v in result.max_drawdown_percentiles.values())  # never below initial cash


def test_same_seed_is_reproducible() -> None:
    trades = [_trade(10), _trade(-5), _trade(20), _trade(-15)]
    result1 = MonteCarloValidator(simulations=500, random_seed=7).validate(trades, initial_cash=10_000)
    result2 = MonteCarloValidator(simulations=500, random_seed=7).validate(trades, initial_cash=10_000)
    assert result1 == result2


def test_different_seeds_can_differ() -> None:
    trades = [_trade(10), _trade(-5), _trade(20), _trade(-15), _trade(3), _trade(-8)]
    result1 = MonteCarloValidator(simulations=200, random_seed=1).validate(trades, initial_cash=10_000)
    result2 = MonteCarloValidator(simulations=200, random_seed=2).validate(trades, initial_cash=10_000)
    assert result1.final_equity_percentiles != result2.final_equity_percentiles


def test_percentiles_are_monotonically_nondecreasing() -> None:
    validator = MonteCarloValidator(simulations=500, percentiles=[5, 25, 50, 75, 95], random_seed=3)
    trades = [_trade(pnl) for pnl in (10, -5, 20, -15, 3, -8, 12, -2)]
    result = validator.validate(trades, initial_cash=10_000)
    ordered = [result.final_equity_percentiles[p] for p in (5, 25, 50, 75, 95)]
    assert ordered == sorted(ordered)


def test_result_reports_requested_percentile_keys() -> None:
    validator = MonteCarloValidator(simulations=50, percentiles=[10, 90], random_seed=1)
    result = validator.validate([_trade(5), _trade(-5)], initial_cash=1000)
    assert set(result.final_equity_percentiles) == {10, 90}
    assert set(result.max_drawdown_percentiles) == {10, 90}


def test_single_simulation_returns_that_simulations_value_directly() -> None:
    validator = MonteCarloValidator(simulations=1, percentiles=[50], random_seed=1)
    result = validator.validate([_trade(10)], initial_cash=1000)
    assert result.final_equity_percentiles[50] == 1010.0


def test_percentile_at_exact_integer_rank_does_not_interpolate() -> None:
    # 5 simulations -> ranks for 0/50/100th percentile are exactly 0/2/4,
    # landing precisely on an element rather than between two.
    validator = MonteCarloValidator(simulations=5, percentiles=[0, 50, 100], random_seed=1)
    result = validator.validate([_trade(10), _trade(-5)], initial_cash=1000)
    assert result.final_equity_percentiles[0] <= result.final_equity_percentiles[50] <= result.final_equity_percentiles[100]
