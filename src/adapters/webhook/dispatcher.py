from __future__ import annotations

from src.adapters.vcs.github_adapter import GitHubVCSProvider
from src.adapters.vcs.gitlab_adapter import GitLabVCSProvider
from src.domain.entities.change_request import ChangeRequest
from src.ports.vcs_provider import VCSNormalizationError, VCSProvider

_PROVIDERS: dict[str, VCSProvider] = {
    "github": GitHubVCSProvider(),
    "gitlab": GitLabVCSProvider(),
}


def normalize_webhook(provider_key: str, raw_payload: dict) -> ChangeRequest:
    provider = _PROVIDERS.get(provider_key.lower())
    if provider is None:
        raise VCSNormalizationError(
            f"unsupported VCS provider '{provider_key}'; supported: {', '.join(_PROVIDERS)}"
        )
    return provider.normalize(raw_payload)
