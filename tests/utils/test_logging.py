import json
import logging

from btengine.utils.logging import JsonLogFormatter, configure_logging


def test_json_log_formatter_emits_valid_json_with_expected_fields() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="btengine.data.coinglass.client",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="coinglass request starting",
        args=None,
        exc_info=None,
    )
    record.endpoint = "/api/futures/price/history"

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "btengine.data.coinglass.client"
    assert payload["message"] == "coinglass request starting"
    assert payload["endpoint"] == "/api/futures/price/history"
    assert "timestamp" in payload


def test_json_log_formatter_includes_exception_info() -> None:
    formatter = JsonLogFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="btengine.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=None,
            exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert "ValueError" in payload["exc_info"]


def test_configure_logging_is_idempotent() -> None:
    root = logging.getLogger("btengine")
    root.handlers.clear()

    configure_logging()
    configure_logging()

    assert len(root.handlers) == 1
    root.handlers.clear()
