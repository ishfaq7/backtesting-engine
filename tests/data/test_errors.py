from btengine.data.errors import (
    AuthenticationError,
    DataLayerError,
    RateLimitExceededError,
    TransientProviderError,
)


def test_authentication_error_carries_structured_context() -> None:
    error = AuthenticationError("bad key", status_code=401, endpoint="/api/x")
    assert isinstance(error, DataLayerError)
    assert error.status_code == 401
    assert error.endpoint == "/api/x"
    assert error.context == {"status_code": 401, "endpoint": "/api/x"}


def test_rate_limit_error_carries_retry_after() -> None:
    error = RateLimitExceededError("slow down", retry_after_seconds=2.5, endpoint="/api/x")
    assert error.retry_after_seconds == 2.5


def test_transient_error_preserves_cause() -> None:
    cause = ValueError("boom")
    error = TransientProviderError("timeout", endpoint="/api/x", cause=cause)
    assert error.__cause__ is cause


def test_repr_includes_context() -> None:
    error = AuthenticationError("bad key", status_code=403, endpoint="/api/x")
    assert "AuthenticationError" in repr(error)
    assert "403" in repr(error)
