"""Structured logging configuration for btengine.

Library modules only ever call ``logging.getLogger(__name__)`` and attach
context via the ``extra=`` kwarg; :func:`configure_logging` is called once
by an application entry point (a script, CLI, or test fixture) to decide
how those records are actually emitted.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

_RESERVED_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}


class JsonLogFormatter(logging.Formatter):
    """Renders each log record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = {
            key: value for key, value in record.__dict__.items() if key not in _RESERVED_RECORD_ATTRS
        }
        if extras:
            payload.update(extras)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Attach a single JSON stream handler to the ``btengine`` logger tree.

    Idempotent: calling this more than once does not duplicate handlers.
    """
    root = logging.getLogger("btengine")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
