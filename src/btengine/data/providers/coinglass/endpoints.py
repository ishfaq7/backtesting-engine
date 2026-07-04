"""CoinGlass v4 endpoint path constants.

Centralized here so that confirming/updating a path against the current
CoinGlass API docs (or reacting to a breaking API change) is a one-file
edit, never a hunt through client or provider code.
"""

from __future__ import annotations

PRICE_OHLC_HISTORY = "/api/futures/price/history"
FUNDING_RATE_OHLC_HISTORY = "/api/futures/funding-rate/ohlc-history"
OPEN_INTEREST_OHLC_HISTORY = "/api/futures/open-interest/ohlc-history"
LIQUIDATION_HISTORY = "/api/futures/liquidation/history"
LONG_SHORT_RATIO_HISTORY = "/api/futures/long-short-ratio/history"
