from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from src.observability.correlation import get_correlation_id
from src.security.redaction import redact_value


class _CorrelationAndRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id() or "-"
        if isinstance(record.msg, str):
            record.msg = redact_value(record.msg)
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s"
    )
    handler.setFormatter(formatter)
    handler.addFilter(_CorrelationAndRedactionFilter())
    root.addHandler(handler)

    # Keep third-party access logs at the same structured format but quieter.
    logging.getLogger("uvicorn.access").setLevel("WARNING")
