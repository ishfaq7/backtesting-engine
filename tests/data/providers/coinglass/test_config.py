import pytest

from btengine.data.errors import ConfigurationError
from btengine.data.providers.coinglass.config import CoinGlassSettings, load_coinglass_settings


@pytest.fixture(autouse=True)
def _clear_coinglass_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(__import__("os").environ):
        if key.startswith("COINGLASS_"):
            monkeypatch.delenv(key, raising=False)


def test_missing_api_key_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        load_coinglass_settings(_env_file=None)


def test_blank_api_key_raises_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        load_coinglass_settings(api_key="   ", _env_file=None)


def test_valid_api_key_is_accepted() -> None:
    settings = load_coinglass_settings(api_key="secret-key", _env_file=None)
    assert settings.api_key.get_secret_value() == "secret-key"


def test_defaults_are_sane() -> None:
    settings = load_coinglass_settings(api_key="secret-key", _env_file=None)
    assert settings.base_url == "https://open-api-v4.coinglass.com"
    assert settings.max_retries == 5
    assert settings.rate_limit_requests == 30


def test_base_url_must_be_https() -> None:
    with pytest.raises(ConfigurationError):
        load_coinglass_settings(api_key="secret-key", base_url="http://insecure.example.com", _env_file=None)


def test_settings_can_be_overridden() -> None:
    settings = load_coinglass_settings(
        api_key="secret-key", max_retries=1, rate_limit_requests=5, _env_file=None
    )
    assert settings.max_retries == 1
    assert settings.rate_limit_requests == 5


def test_api_key_never_appears_in_repr() -> None:
    settings = CoinGlassSettings(api_key="super-secret", _env_file=None)
    assert "super-secret" not in repr(settings)
    assert "super-secret" not in str(settings)
