import json
from typing import Callable

import httpx
import pytest

from btengine.data.errors import (
    AuthenticationError,
    InvalidResponseError,
    RateLimitExceededError,
    TransientProviderError,
)
from btengine.data.providers.coinglass.auth import CoinGlassAuthProvider
from btengine.data.providers.coinglass.client import CoinGlassClient
from btengine.data.providers.coinglass.config import CoinGlassSettings
from btengine.data.providers.coinglass.rate_limiter import TokenBucketRateLimiter
from btengine.data.providers.coinglass.retry import RetryPolicy


class SpyRateLimiter:
    def __init__(self) -> None:
        self.acquire_count = 0

    def acquire(self) -> None:
        self.acquire_count += 1


def _make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    max_retries: int = 0,
    rate_limiter: object | None = None,
) -> tuple[CoinGlassClient, SpyRateLimiter]:
    settings = CoinGlassSettings(api_key="test-key", _env_file=None)
    auth_provider = CoinGlassAuthProvider(settings)
    limiter = rate_limiter or SpyRateLimiter()
    retry_policy = RetryPolicy(
        max_retries=max_retries, base_delay_seconds=0.01, max_delay_seconds=0.05, sleep=lambda s: None
    )
    transport = httpx.MockTransport(handler)
    client = CoinGlassClient(settings, auth_provider, limiter, retry_policy, transport=transport)
    return client, limiter


def test_successful_request_returns_unwrapped_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "msg": "success", "data": [{"a": 1}]})

    client, limiter = _make_client(handler)
    result = client.get("/api/x")
    assert result == [{"a": 1}]
    assert limiter.acquire_count == 1


def test_auth_header_is_sent() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["CG-API-KEY"] = request.headers.get("CG-API-KEY", "")
        return httpx.Response(200, json={"code": "0", "msg": "ok", "data": []})

    client, _ = _make_client(handler)
    client.get("/api/x")
    assert captured["CG-API-KEY"] == "test-key"


def test_401_raises_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "40100", "msg": "unauthorized"})

    client, _ = _make_client(handler)
    with pytest.raises(AuthenticationError) as exc_info:
        client.get("/api/x")
    assert exc_info.value.status_code == 401


def test_429_raises_rate_limit_error_with_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "3"}, json={"code": "42900", "msg": "rate limited"})

    client, _ = _make_client(handler)
    with pytest.raises(RateLimitExceededError) as exc_info:
        client.get("/api/x")
    assert exc_info.value.retry_after_seconds == 3.0


def test_500_raises_transient_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client, _ = _make_client(handler)
    with pytest.raises(TransientProviderError):
        client.get("/api/x")


def test_malformed_json_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="not json")

    client, _ = _make_client(handler)
    with pytest.raises(InvalidResponseError):
        client.get("/api/x")


def test_missing_envelope_code_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    client, _ = _make_client(handler)
    with pytest.raises(InvalidResponseError):
        client.get("/api/x")


def test_error_code_in_envelope_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "40001", "msg": "bad params", "data": None})

    client, _ = _make_client(handler)
    with pytest.raises(InvalidResponseError):
        client.get("/api/x")


def test_timeout_raises_transient_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, _ = _make_client(handler)
    with pytest.raises(TransientProviderError):
        client.get("/api/x")


def test_connect_error_raises_transient_provider_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client, _ = _make_client(handler)
    with pytest.raises(TransientProviderError):
        client.get("/api/x")


def test_generic_4xx_raises_invalid_response_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(418, text="I'm a teapot")

    client, _ = _make_client(handler)
    with pytest.raises(InvalidResponseError):
        client.get("/api/x")


def test_retry_after_header_missing_falls_back_to_backoff() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": "42900", "msg": "rate limited"})

    client, _ = _make_client(handler)
    with pytest.raises(RateLimitExceededError) as exc_info:
        client.get("/api/x")
    assert exc_info.value.retry_after_seconds is None


def test_retry_after_header_non_numeric_is_ignored() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "not-a-number"}, json={"code": "42900", "msg": "x"})

    client, _ = _make_client(handler)
    with pytest.raises(RateLimitExceededError) as exc_info:
        client.get("/api/x")
    assert exc_info.value.retry_after_seconds is None


def test_client_retries_transient_error_and_eventually_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(500, text="internal error")
        return httpx.Response(200, json={"code": "0", "msg": "ok", "data": {"value": 42}})

    client, limiter = _make_client(handler, max_retries=5)
    result = client.get("/api/x")
    assert result == {"value": 42}
    assert attempts["count"] == 3
    assert limiter.acquire_count == 3  # one acquire per attempt


def test_client_close_closes_underlying_http_client() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "0", "msg": "ok", "data": []})

    client, _ = _make_client(handler)
    with client:
        client.get("/api/x")
    assert client._http.is_closed


def test_verify_connection_succeeds_against_supported_coins() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"code": "0", "msg": "ok", "data": ["BTC", "ETH"]})

    client, _ = _make_client(handler)
    client.verify_connection()  # must not raise
    assert calls == ["/api/futures/supported-coins"]


def test_verify_connection_raises_on_bad_credentials() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "40100", "msg": "unauthorized"})

    client, _ = _make_client(handler)
    with pytest.raises(AuthenticationError):
        client.verify_connection()


def test_body_code_401_with_http_200_raises_authentication_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "401", "msg": "invalid key", "data": None})

    client, _ = _make_client(handler)
    with pytest.raises(AuthenticationError):
        client.get("/api/x")


def test_body_code_429_with_http_200_raises_rate_limit_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": "429", "msg": "rate limited", "data": None})

    client, _ = _make_client(handler)
    with pytest.raises(RateLimitExceededError) as exc_info:
        client.get("/api/x")
    assert exc_info.value.retry_after_seconds is None


@pytest.mark.parametrize("code", ["408", "500"])
def test_body_code_transient_with_http_200_raises_transient_provider_error(code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": code, "msg": "server hiccup", "data": None})

    client, _ = _make_client(handler)
    with pytest.raises(TransientProviderError):
        client.get("/api/x")


@pytest.mark.parametrize("code", ["400", "404", "405", "422"])
def test_body_code_request_errors_with_http_200_raise_invalid_response_error(code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": code, "msg": "bad request", "data": None})

    client, _ = _make_client(handler)
    with pytest.raises(InvalidResponseError):
        client.get("/api/x")
