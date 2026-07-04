"""Raw CoinGlass JSON to canonical schema translation.

Field names below are sourced from CoinGlass's official endpoint
documentation (https://github.com/coinglass-official/coinglass-api-skills)
as of this writing:

- ``time`` is a millisecond epoch integer on every history endpoint.
- Price history rows are ``{time, open, high, low, close, volume_usd}``.
- Funding-rate and open-interest history are themselves OHLC-shaped bars
  (``{time, open, high, low, close}``); this adapter uses the bar's
  ``close`` as the single representative value for that interval, which is
  the standard convention for treating an OHLC series as a scalar series.
- Long/short ratio endpoints report a percentage pair per side (e.g.
  ``global_account_long_percent`` / ``global_account_short_percent``) that
  CoinGlass has been observed to express either as fractions (~1.0 total)
  or percentages (~100 total); both are normalized to fractions here.
- The exact field names for the liquidation history endpoint were not
  confirmed from public documentation at the time of writing (liquidation
  data isn't naturally OHLC-shaped like the others) — **confirm
  ``long_liquidation_usd``/``short_liquidation_usd`` against a live
  response before relying on this in production.**

Every field name is either a local constant or named directly at each
``record[...]``/``require_fields`` call, so correcting one against a live
response is a one- or two-line change, never a rewrite of the mapping logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from btengine.data.errors import InvalidResponseError, NormalizationError
from btengine.data.schema import (
    Candle,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
    SupportedMarket,
    Timeframe,
)
from btengine.data.validation import coerce_float, ensure_list_of_dicts, require_fields


def _epoch_ms_to_datetime(value: Any, *, endpoint: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError, OverflowError) as exc:
        raise NormalizationError(
            f"Could not parse epoch-ms timestamp {value!r} from {endpoint}",
            field="time",
            raw_value=value,
        ) from exc


def map_candles(
    raw_data: Any, *, exchange: str, symbol: str, timeframe: Timeframe, endpoint: str
) -> list[Candle]:
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "open", "high", "low", "close", "volume_usd"]
    candles: list[Candle] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            candles.append(
                Candle(
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    open=coerce_float(record, "open", endpoint=endpoint),
                    high=coerce_float(record, "high", endpoint=endpoint),
                    low=coerce_float(record, "low", endpoint=endpoint),
                    close=coerce_float(record, "close", endpoint=endpoint),
                    volume=coerce_float(record, "volume_usd", endpoint=endpoint),
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"Candle from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return candles


def map_funding_rates(
    raw_data: Any, *, exchange: str, symbol: str, endpoint: str
) -> list[FundingRate]:
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "close"]
    results: list[FundingRate] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            results.append(
                FundingRate(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    funding_rate=coerce_float(record, "close", endpoint=endpoint),
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"FundingRate from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return results


def map_open_interest(
    raw_data: Any, *, exchange: str, symbol: str, endpoint: str
) -> list[OpenInterest]:
    """Map an open-interest OHLC bar, requested with ``unit=usd`` (see
    ``provider.py``), so ``close`` is unambiguously a USD value and both
    ``open_interest`` and ``open_interest_value_usd`` are populated from it.
    """
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "close"]
    results: list[OpenInterest] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            value_usd = coerce_float(record, "close", endpoint=endpoint)
            results.append(
                OpenInterest(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    open_interest=value_usd,
                    open_interest_value_usd=value_usd,
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"OpenInterest from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return results


def map_liquidations(
    raw_data: Any, *, exchange: str, symbol: str, endpoint: str
) -> list[Liquidation]:
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "long_liquidation_usd", "short_liquidation_usd"]
    results: list[Liquidation] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            results.append(
                Liquidation(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    long_liquidation_usd=coerce_float(record, "long_liquidation_usd", endpoint=endpoint),
                    short_liquidation_usd=coerce_float(record, "short_liquidation_usd", endpoint=endpoint),
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"Liquidation from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return results


def map_long_short_ratios(
    raw_data: Any,
    *,
    exchange: str,
    symbol: str,
    endpoint: str,
    long_field: str,
    short_field: str,
) -> list[LongShortRatio]:
    """Map any of CoinGlass's long/short ratio endpoints (global account,
    top-trader account, or top-trader position) to the canonical schema.

    ``long_field``/``short_field`` are the endpoint-specific percentage
    field names (e.g. ``global_account_long_percent`` /
    ``global_account_short_percent``, or the ``top_account_*`` /
    ``top_position_*`` equivalents) — the three endpoints share the same
    shape and only differ in these field names.
    """
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", long_field, short_field]
    results: list[LongShortRatio] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        long_ratio = coerce_float(record, long_field, endpoint=endpoint)
        short_ratio = coerce_float(record, short_field, endpoint=endpoint)
        # CoinGlass has been observed to report this pair either as fractions
        # (summing to ~1.0) or as percentages (summing to ~100). Normalize to
        # fractions so the canonical schema's 0-1 constraint always holds.
        if long_ratio + short_ratio > 1.5:
            long_ratio /= 100
            short_ratio /= 100
        try:
            results.append(
                LongShortRatio(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    long_account_ratio=long_ratio,
                    short_account_ratio=short_ratio,
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"LongShortRatio from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return results


def map_supported_markets(raw_data: Any, *, endpoint: str) -> list[SupportedMarket]:
    """Map the ``supported-exchange-pairs`` response.

    Unlike every other endpoint here, this one's ``data`` is a dict keyed
    by exchange name, mapping to a list of ``{instrument_id, base_asset,
    quote_asset, ...}`` objects — not a flat list of records.
    """
    if not isinstance(raw_data, dict):
        raise InvalidResponseError(
            f"Expected a dict payload from {endpoint}, got {type(raw_data).__name__}",
            endpoint=endpoint,
            payload_excerpt=str(raw_data)[:500],
        )

    required = ["instrument_id", "base_asset", "quote_asset"]
    markets: list[SupportedMarket] = []
    for exchange, pairs in raw_data.items():
        if not isinstance(pairs, list):
            raise InvalidResponseError(
                f"Expected a list of pairs for exchange {exchange!r} from {endpoint}, "
                f"got {type(pairs).__name__}",
                endpoint=endpoint,
                payload_excerpt=str(pairs)[:500],
            )
        for record in pairs:
            if not isinstance(record, dict):
                raise InvalidResponseError(
                    f"Expected pair objects for exchange {exchange!r} from {endpoint}, "
                    f"got {type(record).__name__}",
                    endpoint=endpoint,
                    payload_excerpt=str(record)[:500],
                )
            require_fields(record, required, endpoint=endpoint)
            try:
                markets.append(
                    SupportedMarket(
                        exchange=exchange,
                        instrument_id=record["instrument_id"],
                        base_asset=record["base_asset"],
                        quote_asset=record["quote_asset"],
                    )
                )
            except ValidationError as exc:
                raise NormalizationError(
                    f"SupportedMarket from {endpoint} failed canonical validation: {exc}",
                    raw_value=record,
                ) from exc
    return markets
