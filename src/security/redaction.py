"""Secret/token redaction for logs, error responses, and audit payloads.

This is a best-effort, defense-in-depth layer — not a substitute for never
putting secrets in these payloads in the first place.
"""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(pass(word)?|secret|token|api[_-]?key|authorization|credential|private[_-]?key)", re.IGNORECASE
)
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
_AWS_KEY_PATTERN = re.compile(r"\bAKIA[0-9A-Z]{16}\b")

REDACTED = "***REDACTED***"


def redact_value(value: str) -> str:
    value = _BEARER_PATTERN.sub(f"Bearer {REDACTED}", value)
    value = _AWS_KEY_PATTERN.sub(REDACTED, value)
    return value


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redacts values whose key looks sensitive, and scrubs known
    secret patterns out of remaining string values."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_KEY_PATTERN.search(str(key)):
            result[key] = REDACTED
        elif isinstance(value, dict):
            result[key] = redact_mapping(value)
        elif isinstance(value, list):
            result[key] = [redact_mapping(v) if isinstance(v, dict) else _redact_scalar(v) for v in value]
        else:
            result[key] = _redact_scalar(value)
    return result


def _redact_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return redact_value(value)
    return value
