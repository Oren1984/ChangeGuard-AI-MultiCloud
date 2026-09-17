from __future__ import annotations

from typing import Protocol

from src.domain.entities.change_request import ChangeRequest


class VCSNormalizationError(Exception):
    """Raised when a raw provider payload cannot be normalized safely."""


class VCSProvider(Protocol):
    """Translates a provider-specific webhook payload (GitHub, GitLab, ...)
    into the normalized, provider-independent ChangeRequest the rest of the
    system operates on. New providers plug in here without touching domain
    or application code.
    """

    provider_name: str

    def normalize(self, raw_payload: dict) -> ChangeRequest:
        ...
