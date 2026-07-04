from datetime import datetime, timezone

from btengine.backtest.engine import BacktestResult
from btengine.backtest.performance_tracker import PerformanceSummary
from btengine.integrations.web_dashboard import DashboardPublisher

UTC = timezone.utc


class ConformingPublisher:
    def __init__(self) -> None:
        self.results = []
        self.points = []

    def publish_result(self, result: BacktestResult) -> None:
        self.results.append(result)

    def publish_equity_point(self, timestamp, equity: float) -> None:
        self.points.append((timestamp, equity))


class NonConforming:
    def publish_result(self, result) -> None:
        pass  # missing publish_equity_point


def test_conforming_publisher_satisfies_protocol() -> None:
    assert isinstance(ConformingPublisher(), DashboardPublisher)


def test_partial_implementation_does_not_satisfy_protocol() -> None:
    assert not isinstance(NonConforming(), DashboardPublisher)


def test_conforming_publisher_behaves_as_expected() -> None:
    publisher: DashboardPublisher = ConformingPublisher()
    result = BacktestResult(
        trades=[],
        equity_curve=[(datetime(2024, 1, 1, tzinfo=UTC), 10_000.0)],
        summary=PerformanceSummary(
            initial_cash=10_000, final_equity=10_000, total_return=0.0, max_drawdown=0.0,
            num_trades=0, win_rate=None, profit_factor=None,
        ),
    )
    publisher.publish_result(result)
    publisher.publish_equity_point(datetime(2024, 1, 1, tzinfo=UTC), 10_000.0)
    assert publisher.results == [result]
    assert publisher.points == [(datetime(2024, 1, 1, tzinfo=UTC), 10_000.0)]
