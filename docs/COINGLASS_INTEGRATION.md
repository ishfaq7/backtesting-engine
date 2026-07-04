# CoinGlass Integration — Startup Plan

Scope of this document: exactly which CoinGlass endpoints this codebase
calls, why each was chosen for the Startup plan, how each maps to the
proprietary strategy's planned analysis components (per
`docs/STRATEGY_AND_DATA_LAYER.md` §2), and what's likely needed later.

Source of truth for paths, parameters, and plan limits: CoinGlass's
official endpoint documentation
(https://github.com/coinglass-official/coinglass-api-skills) and published
pricing page, as of this writing. CoinGlass does not expose a machine-
readable schema, so **treat field names as best-effort and confirm against
a live response** — every place that matters is called out below and is a
one-line change in `mapper.py`/`endpoints.py` if wrong.

## 1. Startup plan constraints baked into this integration

| | Startup plan |
|---|---|
| Endpoints | 130+ |
| Rate limit | 80 requests/minute (`COINGLASS_RATE_LIMIT_REQUESTS` default) |
| Commercial use | Not permitted (personal/research use only) |
| Supported intervals | 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d |
| History length | 30m→90d, 1h/2h/4h→180d, 6h/8h/12h→360d, 1d→all-time |

`btengine/data/providers/coinglass/plan_limits.py` encodes this table and
rejects any request outside it — with a clear `PlanRestrictionError` —
before an HTTP call is made. 1m/5m/15m intraday data and 1w bars are not
available on this plan and are not wired into the client.

## 2. Supported endpoints

| Endpoint | Path | Canonical model | Provider method |
|---|---|---|---|
| Price history (OHLC) | `/api/futures/price/history` | `Candle` | `get_ohlcv` |
| Funding rate history | `/api/futures/funding-rate/history` | `FundingRate` | `get_funding_rate` |
| Funding rate, OI-weighted | `/api/futures/funding-rate/oi-weight-history` | `FundingRate` | `get_funding_rate_oi_weighted` |
| Open interest history | `/api/futures/open-interest/history` | `OpenInterest` | `get_open_interest` |
| Open interest, aggregated | `/api/futures/open-interest/aggregated-history` | `OpenInterest` | `get_open_interest_aggregated` |
| Liquidation history | `/api/futures/liquidation/history` | `Liquidation` | `get_liquidations` |
| Global long/short account ratio | `/api/futures/global-long-short-account-ratio/history` | `LongShortRatio` | `get_long_short_ratio` |
| Top-trader account ratio | `/api/futures/top-long-short-account-ratio/history` | `LongShortRatio` | `get_top_long_short_account_ratio` |
| Top-trader position ratio | `/api/futures/top-long-short-position-ratio/history` | `LongShortRatio` | `get_top_long_short_position_ratio` |
| Supported coins | `/api/futures/supported-coins` | — | `verify_connection()` (via client) |
| Supported exchange pairs | `/api/futures/supported-exchange-pairs` | `SupportedMarket` | `get_supported_markets` |

The first five (`get_ohlcv` … `get_long_short_ratio`) are part of the
provider-agnostic `MarketDataProvider` interface every provider must
implement. The OI-weighted funding rate, aggregated OI, and top-trader
ratio methods are CoinGlass-specific extensions on `CoinGlassDataProvider`
— they reuse the same canonical models (they're the same shape, just a
different source/aggregation), so no schema bloat was needed to expose them.

Endpoints **not** included: 1m/5m/15m intraday granularity, L2/L3 order
book, options, spot, ETF, and on-chain data. These are either gated to
Standard/Professional/Enterprise or weren't confirmed as part of the
futures data this integration targets — see §4.

## 3. How each endpoint maps to the proprietary strategy

Per the Strategy Framework design (`docs/STRATEGY_AND_DATA_LAYER.md`), the
strategy will have independent `MarketAnalyzer` components. This is a data
*availability* map, not strategy logic — no thresholds, weights, or
decisions are implied here.

- **Funding Rate Analysis** → `get_funding_rate` (per-exchange rate) and
  `get_funding_rate_oi_weighted` (cross-exchange, OI-weighted average — a
  cleaner aggregate signal than any single exchange's rate, useful for
  filtering out one exchange's idiosyncratic funding spikes).
- **Open Interest Analysis** → `get_open_interest` (per-exchange) and
  `get_open_interest_aggregated` (market-wide OI trend, exchange-agnostic).
- **Premium/Discount Analysis** → `get_ohlcv` across exchanges/instruments
  for the same underlying (e.g. perp vs. index or spot price) — the price
  data this integration already provides is the raw input; the
  premium/discount *calculation* itself belongs to the strategy plugin.
- **Liquidity Analysis** → `get_liquidations` (realized liquidation
  volume, a proxy for forced-flow liquidity events) and the long/short
  ratio endpoints (`get_long_short_ratio`,
  `get_top_long_short_account_ratio`, `get_top_long_short_position_ratio`)
  as positioning-crowdedness inputs — global retail positioning vs.
  top-trader positioning are genuinely different signals (retail is
  frequently on the other side of top traders at extremes).
- **Scoring Model / Risk / No-Trade / Trade & Position Management / Exit
  Rules** — these consume the *outputs* of the analyzers above (and
  portfolio state from the Backtesting Engine), not CoinGlass data
  directly; no additional endpoint is implied by these components.

## 4. Additional data likely needed later

- **Confirm real field names against a live API key.** Every mapper
  documents its assumption inline; `long_liquidation_usd`/
  `short_liquidation_usd` in particular were not confirmed from public
  docs and are the highest-priority thing to verify first.
- **Taker buy/sell volume** (`/api/futures/taker-buy-sell-volume/exchange-list`)
  — a direct order-flow-pressure metric that could sharpen Liquidity
  Analysis beyond liquidations alone. Available on Startup; not wired in
  yet since it wasn't part of the original five data types.
- **Liquidation heatmaps/maps** (`liquidation/heatmap/model*`,
  `liquidation/map`) — visual/derived liquidation-cluster data, useful for
  identifying likely stop-hunt zones; more of a discretionary/visual tool
  than a clean backtestable time series, so deferred.
- **Net long/short position change** (`/api/futures/net-position/history`)
  — a flow metric (position *change*, not just ratio) that could
  complement the long/short ratio endpoints already wired in.
- **1-minute/5-minute granularity** — only available on Standard ($299/mo)
  and above. If the strategy needs finer entry/exit timing than 30m bars
  allow, this is a plan upgrade, not a code change (the plan-limit table
  is the only thing that would need updating).
- **Spot market data** — this integration is futures-only; if the
  strategy's Premium/Discount Analysis wants a spot-vs-perp basis, spot
  price history (`/api/spot/price/history`) would need its own adapter
  method (same client/mapper pattern, new endpoint + canonical reuse of
  `Candle`).
- **Order book depth (L2/L3)** — likely gated above Startup; would matter
  for realistic execution/slippage modeling in the Backtesting Engine's
  execution simulator, not for the current historical-data scope.
