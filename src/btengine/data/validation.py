"""Generic shape validation for raw provider responses.

Runs *before* normalization: confirms a raw payload has the basic shape a
mapper needs (a list of objects, required keys present, numeric fields are
actually numeric) and raises a structured
:class:`~btengine.data.errors.InvalidResponseError` instead of letting a
``KeyError``/``TypeError``/``ValueError`` propagate out of a mapping
function. Provider-specific field *names* are not this module's concern —
only that the payload matches a shape any mapper could safely consume.
"""

from __future__ import annotations

from typing import Any

from btengine.data.errors import InvalidResponseError


def ensure_list_of_dicts(data: Any, *, endpoint: str) -> list[dict[str, Any]]:
    """Validate that ``data`` is a list of JSON objects."""
    if data is None:
        raise InvalidResponseError(
            f"Response for {endpoint} had no data payload", endpoint=endpoint
        )
    if not isinstance(data, list):
        raise InvalidResponseError(
            f"Expected a list payload from {endpoint}, got {type(data).__name__}",
            endpoint=endpoint,
            payload_excerpt=str(data)[:500],
        )
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise InvalidResponseError(
                f"Expected list items from {endpoint} to be objects, "
                f"item {index} was {type(item).__name__}",
                endpoint=endpoint,
                payload_excerpt=str(item)[:500],
            )
    return data


def require_fields(record: dict[str, Any], required: list[str], *, endpoint: str) -> None:
    """Validate that every field in ``required`` is present in ``record``."""
    missing = [field for field in required if field not in record]
    if missing:
        raise InvalidResponseError(
            f"Record from {endpoint} is missing required fields: {missing}",
            endpoint=endpoint,
            payload_excerpt=str(record)[:500],
        )


def coerce_float(record: dict[str, Any], field: str, *, endpoint: str) -> float:
    """Extract ``field`` from ``record`` as a float, or raise a structured error."""
    value = record.get(field)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidResponseError(
            f"Record from {endpoint} had a non-numeric value for '{field}': {value!r}",
            endpoint=endpoint,
            payload_excerpt=str(record)[:500],
        ) from exc
