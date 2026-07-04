"""CoinGlass v4 endpoint path constants, scoped to the Startup plan.

Paths and required/optional query parameters are sourced from CoinGlass's
official endpoint documentation
(https://github.com/coinglass-official/coinglass-api-skills) as of this
writing. Endpoints known to require Standard/Professional/Enterprise (1m/5m/
15m intraday granularity, L2/L3 order book, options, ETF, ETF holdings) are
deliberately not included here — they are not callable on Startup and
including them would invite confusing 4xx errors at runtime. See
``docs/COINGLASS_INTEGRATION.md`` for the full endpoint-to-plan rationale.

Centralizing paths here means confirming/updating one against a live
response, or reacting to a CoinGlass API change, is a one-file edit.
"""

from __future__ import annotations

# --- Discovery / metadata (used for connection verification and instrument
# discovery; available on every plan tier including Startup) ---
SUPPORTED_COINS = "/api/futures/supported-coins"
SUPPORTED_EXCHANGES = "/api/futures/supported-exchanges"
SUPPORTED_EXCHANGE_PAIRS = "/api/futures/supported-exchange-pairs"

# --- Price ---
PRICE_OHLC_HISTORY = "/api/futures/price/history"

# --- Funding Rate ---
FUNDING_RATE_HISTORY = "/api/futures/funding-rate/history"
FUNDING_RATE_OI_WEIGHT_HISTORY = "/api/futures/funding-rate/oi-weight-history"

# --- Open Interest ---
OPEN_INTEREST_HISTORY = "/api/futures/open-interest/history"
OPEN_INTEREST_AGGREGATED_HISTORY = "/api/futures/open-interest/aggregated-history"

# --- Liquidations ---
LIQUIDATION_HISTORY = "/api/futures/liquidation/history"
LIQUIDATION_AGGREGATED_HISTORY = "/api/futures/liquidation/aggregated-history"

# --- Long/Short Ratio ---
GLOBAL_LONG_SHORT_ACCOUNT_RATIO_HISTORY = "/api/futures/global-long-short-account-ratio/history"
TOP_LONG_SHORT_ACCOUNT_RATIO_HISTORY = "/api/futures/top-long-short-account-ratio/history"
TOP_LONG_SHORT_POSITION_RATIO_HISTORY = "/api/futures/top-long-short-position-ratio/history"

# CoinGlass caps every history-style endpoint at this many rows per call;
# larger ranges require paging by advancing start_time (see provider.py).
MAX_ROWS_PER_REQUEST = 1000
