"""Resolves CoinGlass credentials into request headers.

Kept separate from :mod:`client` so that *where* the credential comes from
(an env var today; a secrets manager or key-rotation service later) can
change without touching request/transport logic.
"""

from __future__ import annotations

from btengine.data.providers.coinglass.config import CoinGlassSettings


class CoinGlassAuthProvider:
    """Produces the ``CG-API-KEY`` header for every outgoing request."""

    def __init__(self, settings: CoinGlassSettings) -> None:
        self._settings = settings

    def auth_headers(self) -> dict[str, str]:
        return {"CG-API-KEY": self._settings.api_key.get_secret_value()}
