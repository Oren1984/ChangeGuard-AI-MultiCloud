"""Optional external AI provider adapter.

Disabled by default. Only activates when AI_PROVIDER=external and both
AI_EXTERNAL_BASE_URL and AI_EXTERNAL_API_KEY are set via environment
configuration (see src/api/dependencies for wiring). No default execution
path, and no automated test, depends on this adapter making a real network
call — it must never be required for local development or CI.

The wire format below targets a generic OpenAI-compatible chat completions
endpoint returning a JSON object matching AIAssessment's fields; a real
integration would adapt the response-parsing section to its provider.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_request import ChangeRequest
from src.domain.enums.risk_level import RiskLevel
from src.ports.ai_provider import AIProviderError


class ExternalAIProvider:
    name = "external-ai"

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 10.0) -> None:
        if not base_url or not api_key:
            raise AIProviderError("external AI provider is not configured (missing base_url/api_key)")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def analyze(self, change: ChangeRequest) -> AIAssessment:
        request_body = {
            "change_id": change.change_id,
            "repository": change.repository,
            "change_type": change.change_type.value,
            "changed_files": list(change.changed_files),
            "environment_target": change.environment_target.value,
        }
        req = urllib.request.Request(
            url=f"{self._base_url}/v1/changeguard/analyze",
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise AIProviderError(f"external AI provider request failed: {exc}") from exc

        try:
            return AIAssessment(
                provider_name=self.name,
                summary=str(raw["summary"]),
                impact_map=tuple(raw.get("impact_map", [])),
                dependency_concerns=tuple(raw.get("dependency_concerns", [])),
                rollback_considerations=tuple(raw.get("rollback_considerations", [])),
                cab_executive_brief=str(raw.get("cab_executive_brief", "")),
                recommended_reviewer_roles=tuple(raw.get("recommended_reviewer_roles", [])),
                referenced_evidence=tuple(raw.get("referenced_evidence", [])),
                recommended_route=str(raw.get("recommended_route", "CAB_REVIEW_REQUIRED")),
                suggested_risk_level=RiskLevel[str(raw.get("suggested_risk_level", "MEDIUM")).upper()],
                confidence=float(raw.get("confidence", 0.0)),
                raw_response=raw,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise AIProviderError(f"external AI provider returned an unparsable response: {exc}") from exc
