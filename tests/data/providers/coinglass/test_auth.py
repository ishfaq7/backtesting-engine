from btengine.data.providers.coinglass.auth import CoinGlassAuthProvider
from btengine.data.providers.coinglass.config import CoinGlassSettings


def test_auth_headers_contains_cg_api_key() -> None:
    settings = CoinGlassSettings(api_key="my-secret-key", _env_file=None)
    provider = CoinGlassAuthProvider(settings)
    headers = provider.auth_headers()
    assert headers == {"CG-API-KEY": "my-secret-key"}
