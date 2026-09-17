from __future__ import annotations

from typing import Protocol

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_request import ChangeRequest


class AIProviderError(Exception):
    """Raised when a provider cannot produce a result at all (timeout, outage,
    malformed transport response). The pipeline must fail closed on this."""


class AIProvider(Protocol):
    """Explicit abstraction boundary for any AI backend (mock or external).

    Implementations must be side-effect free with respect to the change under
    review: they may only *read* the ChangeRequest and return an advisory
    AIAssessment. They must never merge code, call cloud APIs, or execute
    commands.
    """

    name: str

    def analyze(self, change: ChangeRequest) -> AIAssessment:
        """Return an advisory assessment. Raise AIProviderError on failure."""
        ...
