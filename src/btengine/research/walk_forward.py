"""Walk-forward window splitting.

Pure date-range arithmetic: given a total span and train/test period
lengths, produce a sequence of rolling (train, test) window pairs. This
decides nothing about a strategy or a backtest — it only describes *which
sub-ranges* a caller (typically :mod:`batch_backtest`) should run against.
Running the actual in-sample/out-of-sample backtests per window, and
comparing their performance, is the caller's responsibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from btengine.research.errors import ValidationConfigError


@dataclass(frozen=True)
class WalkForwardWindow:
    """One rolling train/test pair."""

    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime


class WalkForwardSplitter:
    """Splits ``[start, end]`` into rolling train/test windows."""

    def __init__(
        self, *, train_period: timedelta, test_period: timedelta, step: timedelta | None = None
    ) -> None:
        if train_period <= timedelta(0):
            raise ValidationConfigError("train_period must be positive")
        if test_period <= timedelta(0):
            raise ValidationConfigError("test_period must be positive")
        if step is not None and step <= timedelta(0):
            raise ValidationConfigError("step must be positive")
        self._train_period = train_period
        self._test_period = test_period
        self._step = step or test_period

    def split(self, start: datetime, end: datetime) -> list[WalkForwardWindow]:
        """Return every complete (train, test) window that fits in ``[start, end]``.

        A window is only included if both its train and test periods fit
        entirely within the range — a trailing partial window is dropped
        rather than silently returning a shorter-than-requested test period.
        """
        if start.tzinfo is None or end.tzinfo is None:
            raise ValidationConfigError("start/end must be timezone-aware")
        if start >= end:
            raise ValidationConfigError("start must be before end")

        windows: list[WalkForwardWindow] = []
        train_start = start
        while True:
            train_end = train_start + self._train_period
            test_start = train_end
            test_end = test_start + self._test_period
            if test_end > end:
                break
            windows.append(WalkForwardWindow(train_start, train_end, test_start, test_end))
            train_start += self._step
        return windows
