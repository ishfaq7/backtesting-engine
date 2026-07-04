import pytest

from btengine.data.providers.coinglass.rate_limiter import TokenBucketRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_constructor_rejects_nonpositive_arguments() -> None:
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(0, 60)
    with pytest.raises(ValueError):
        TokenBucketRateLimiter(10, 0)


def test_acquire_does_not_sleep_while_tokens_available() -> None:
    clock = FakeClock()
    sleeps: list[float] = []
    limiter = TokenBucketRateLimiter(3, 60, clock=clock, sleep=sleeps.append)

    limiter.acquire()
    limiter.acquire()
    limiter.acquire()

    assert sleeps == []


def test_acquire_sleeps_once_tokens_are_exhausted() -> None:
    clock = FakeClock()
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.advance(seconds)

    limiter = TokenBucketRateLimiter(2, 60, clock=clock, sleep=fake_sleep)
    limiter.acquire()
    limiter.acquire()
    limiter.acquire()  # exhausted: must wait for refill

    assert len(sleeps) == 1
    # refill rate is 2/60 tokens/sec; needed 1 token => 30s wait
    assert sleeps[0] == pytest.approx(30.0)


def test_tokens_refill_over_time() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(2, 60, clock=clock, sleep=lambda s: None)
    limiter.acquire()
    limiter.acquire()
    assert limiter.available_tokens == pytest.approx(0.0)

    clock.advance(30)  # half the period => 1 token back
    assert limiter.available_tokens == pytest.approx(1.0)


def test_tokens_never_exceed_max() -> None:
    clock = FakeClock()
    limiter = TokenBucketRateLimiter(2, 60, clock=clock, sleep=lambda s: None)
    clock.advance(1000)
    assert limiter.available_tokens == pytest.approx(2.0)
