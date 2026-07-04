import pytest

from btengine.data.errors import (
    AuthenticationError,
    InvalidResponseError,
    RateLimitExceededError,
    TransientProviderError,
)
from btengine.data.providers.coinglass.retry import RetryPolicy


def _policy(max_retries: int = 3, sleeps: list[float] | None = None) -> RetryPolicy:
    sleeps = sleeps if sleeps is not None else []
    return RetryPolicy(
        max_retries=max_retries,
        base_delay_seconds=0.1,
        max_delay_seconds=10,
        sleep=sleeps.append,
        jitter=lambda: 1.0,  # no randomness: deterministic delays
    )


def test_constructor_validates_arguments() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=-1, base_delay_seconds=1, max_delay_seconds=1)
    with pytest.raises(ValueError):
        RetryPolicy(max_retries=1, base_delay_seconds=0, max_delay_seconds=1)


def test_succeeds_on_first_attempt_without_sleeping() -> None:
    sleeps: list[float] = []
    policy = _policy(sleeps=sleeps)
    result = policy.run(lambda: "ok")
    assert result == "ok"
    assert sleeps == []


def test_retries_transient_errors_then_succeeds() -> None:
    sleeps: list[float] = []
    policy = _policy(max_retries=3, sleeps=sleeps)
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TransientProviderError("boom", endpoint="/x")
        return "ok"

    result = policy.run(flaky)
    assert result == "ok"
    assert attempts["count"] == 3
    assert len(sleeps) == 2


def test_exhausting_retries_reraises() -> None:
    policy = _policy(max_retries=2)

    def always_fails() -> None:
        raise TransientProviderError("boom", endpoint="/x")

    with pytest.raises(TransientProviderError):
        policy.run(always_fails)


def test_rate_limit_error_uses_retry_after_hint() -> None:
    sleeps: list[float] = []
    policy = _policy(max_retries=1, sleeps=sleeps)
    attempts = {"count": 0}

    def rate_limited_once() -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RateLimitExceededError("slow down", retry_after_seconds=5.0, endpoint="/x")
        return "ok"

    result = policy.run(rate_limited_once)
    assert result == "ok"
    assert sleeps == [5.0]


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("bad key", status_code=401, endpoint="/x"),
        InvalidResponseError("bad shape", endpoint="/x"),
    ],
)
def test_non_retryable_errors_propagate_immediately(error: Exception) -> None:
    sleeps: list[float] = []
    policy = _policy(max_retries=5, sleeps=sleeps)
    calls = {"count": 0}

    def raiser() -> None:
        calls["count"] += 1
        raise error

    with pytest.raises(type(error)):
        policy.run(raiser)

    assert calls["count"] == 1
    assert sleeps == []


def test_backoff_delay_is_capped_at_max_delay() -> None:
    sleeps: list[float] = []
    policy = RetryPolicy(
        max_retries=10, base_delay_seconds=1, max_delay_seconds=3, sleep=sleeps.append, jitter=lambda: 1.0
    )
    attempts = {"count": 0}

    def always_transient() -> None:
        attempts["count"] += 1
        raise TransientProviderError("boom", endpoint="/x")

    with pytest.raises(TransientProviderError):
        policy.run(always_transient)

    assert all(delay <= 3 for delay in sleeps)
