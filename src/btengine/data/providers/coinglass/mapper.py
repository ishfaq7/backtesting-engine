"""Raw CoinGlass JSON to canonical schema translation.

Field names below reflect CoinGlass API v4's typical conventions
(millisecond epoch timestamps under ``time``, ``open``/``high``/``low``/
``close``/``volume`` for OHLC bars, etc.). CoinGlass does not publish a
machine-readable response schema, so **confirm the exact field names
against a live response for your subscription tier before relying on this
in production.** Every field name lives in the small, local constant lists
below (or is named directly at each ``record[...]``/``require_fields``
call) — adjusting one is a one- or two-line change, never a rewrite of the
mapping logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from btengine.data.errors import NormalizationError
from btengine.data.schema import (
    Candle,
    FundingRate,
    Liquidation,
    LongShortRatio,
    OpenInterest,
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
    required = ["time", "open", "high", "low", "close", "volume"]
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
                    volume=coerce_float(record, "volume", endpoint=endpoint),
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
    required = ["time", "fundingRate"]
    results: list[FundingRate] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            results.append(
                FundingRate(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    funding_rate=coerce_float(record, "fundingRate", endpoint=endpoint),
                    predicted_funding_rate=(
                        coerce_float(record, "predictedFundingRate", endpoint=endpoint)
                        if "predictedFundingRate" in record
                        else None
                    ),
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
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "openInterest"]
    results: list[OpenInterest] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            results.append(
                OpenInterest(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    open_interest=coerce_float(record, "openInterest", endpoint=endpoint),
                    open_interest_value_usd=(
                        coerce_float(record, "openInterestValue", endpoint=endpoint)
                        if "openInterestValue" in record
                        else None
                    ),
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
    required = ["time", "longVolUsd", "shortVolUsd"]
    results: list[Liquidation] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        try:
            results.append(
                Liquidation(
                    exchange=exchange,
                    symbol=symbol,
                    timestamp=_epoch_ms_to_datetime(record["time"], endpoint=endpoint),
                    long_liquidation_usd=coerce_float(record, "longVolUsd", endpoint=endpoint),
                    short_liquidation_usd=coerce_float(record, "shortVolUsd", endpoint=endpoint),
                )
            )
        except ValidationError as exc:
            raise NormalizationError(
                f"Liquidation from {endpoint} failed canonical validation: {exc}", raw_value=record
            ) from exc
    return results


def map_long_short_ratios(
    raw_data: Any, *, exchange: str, symbol: str, endpoint: str
) -> list[LongShortRatio]:
    records = ensure_list_of_dicts(raw_data, endpoint=endpoint)
    required = ["time", "longAccount", "shortAccount"]
    results: list[LongShortRatio] = []
    for record in records:
        require_fields(record, required, endpoint=endpoint)
        long_ratio = coerce_float(record, "longAccount", endpoint=endpoint)
        short_ratio = coerce_float(record, "shortAccount", endpoint=endpoint)
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
