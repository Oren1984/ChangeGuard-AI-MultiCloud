from __future__ import annotations

from fastapi import Depends

from src.adapters.ai.external_provider import ExternalAIProvider
from src.adapters.ai.mock_provider import MockAIProvider
from src.config import Settings, get_settings
from src.ports.ai_provider import AIProvider


def get_primary_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    if settings.ai_provider == "external":
        return ExternalAIProvider(
            base_url=settings.ai_external_base_url or "",
            api_key=settings.ai_external_api_key or "",
        )
    return MockAIProvider()


def get_secondary_ai_provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    # The secondary/"second opinion" provider used exclusively for Gate 5
    # (consistency). Always the local deterministic mock, in drift mode,
    # regardless of the primary provider — this keeps the consistency check
    # runnable without any external dependency.
    return MockAIProvider(name="mock-ai-v1-secondary", drift=True)
