"""Deterministic, offline AI provider used by default (no network, no API
keys). It reasons only over fields already present on the ChangeRequest, so
its `referenced_evidence` is grounded by construction — except when a demo
scenario deliberately asks it to fabricate evidence, to exercise Gate 2.

Demo/test scenarios are opted into via `change.metadata["_demo"]`. This is a
POC testing hook, not a production feature — real providers won't have it.
"""

from __future__ import annotations

import hashlib

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_request import ChangeRequest
from src.domain.enums.risk_level import RiskLevel
from src.ports.ai_provider import AIProviderError

_DANGEROUS_SNIPPETS = {
    "dangerous_recommendation": (
        "Recommend running `terraform destroy` directly against production to reset state."
    ),
    "disable_audit": "Recommend temporarily disabling audit logging to speed up the rollout.",
}


def _stable_unit_interval(seed: str) -> float:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


class MockAIProvider:
    """The default local AI provider. Fully deterministic given a ChangeRequest."""

    def __init__(self, name: str = "mock-ai-v1", drift: bool = False) -> None:
        self.name = name
        self.drift = drift

    def analyze(self, change: ChangeRequest) -> AIAssessment:
        scenario = change.metadata.get("_demo")

        if scenario == "provider_unavailable":
            raise AIProviderError("mock provider unavailable (simulated outage)")
        if scenario == "provider_timeout":
            raise AIProviderError("mock provider timed out (simulated)")

        evidence = list(change.changed_files[:10])
        evidence.append(f"repository:{change.repository}")
        evidence.append(f"branch:{change.branch}")
        if change.terraform_plan:
            evidence.extend(rc.address for rc in change.terraform_plan.resource_changes[:10])
        if change.migration_statements:
            evidence.extend(f"migration:{s[:60]}" for s in change.migration_statements[:5])

        if scenario == "fabricated_evidence":
            evidence.append("src/nonexistent_module_never_submitted.py")

        # Comfortably clears the default approval threshold (0.70) for any
        # change_id by construction, so ordinary (non-demo) evaluations are
        # deterministic in outcome even though the exact value varies.
        base_seed = f"{change.change_id}:{self.name}:{'drift' if self.drift else 'primary'}"
        confidence = 0.80 + 0.19 * _stable_unit_interval(base_seed)

        if scenario == "low_confidence":
            confidence = 0.15
        elif scenario == "warning_confidence":
            confidence = 0.55

        suggested_level = self._suggest_risk_level(change)
        recommended_route = self._suggest_route(suggested_level)

        if self.drift and scenario == "inconsistent":
            # Deliberately materially different second opinion, to exercise
            # Gate 5 (consistency) in the inconsistent-AI demo scenario.
            recommended_route = "HARD_BLOCK" if recommended_route != "HARD_BLOCK" else "AUTO_CLEAR"
            confidence = max(0.05, confidence - 0.5)
            suggested_level = RiskLevel.CRITICAL if suggested_level != RiskLevel.CRITICAL else RiskLevel.LOW

        summary = (
            f"Change {change.change_id} in {change.repository}@{change.branch} touches "
            f"{change.changed_file_count} file(s) and targets {change.environment_target.value}."
        )
        rollback = [
            "Rollback plan present." if change.has_rollback_plan else "No rollback plan was submitted.",
        ]
        dependency_concerns = (
            [f"{len(change.service_dependencies)} dependent service(s) may be affected."]
            if change.service_dependencies
            else ["No dependent services declared."]
        )

        if scenario in _DANGEROUS_SNIPPETS:
            summary += " " + _DANGEROUS_SNIPPETS[scenario]

        cab_brief = (
            f"Executive brief: {change.change_type.value} change to {change.repository}, "
            f"risk-relevant evidence includes {len(evidence)} item(s). "
            f"Rollback ready: {change.has_rollback_plan}."
        )

        return AIAssessment(
            provider_name=self.name,
            summary=summary,
            impact_map=tuple(f"affects:{f}" for f in change.changed_files[:10]),
            dependency_concerns=tuple(dependency_concerns),
            rollback_considerations=tuple(rollback),
            cab_executive_brief=cab_brief,
            recommended_reviewer_roles=self._suggest_reviewers(change),
            referenced_evidence=tuple(evidence),
            recommended_route=recommended_route,
            suggested_risk_level=suggested_level,
            confidence=round(min(confidence, 0.99), 4),
            raw_response={"scenario": scenario, "drift": self.drift},
        )

    @staticmethod
    def _suggest_risk_level(change: ChangeRequest) -> RiskLevel:
        if change.change_type.value in ("iam_policy", "db_migration") and change.is_production_target:
            return RiskLevel.HIGH
        if change.is_production_target:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _suggest_route(level: RiskLevel) -> str:
        if level == RiskLevel.CRITICAL:
            return "HARD_BLOCK"
        if level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
            return "CAB_REVIEW_REQUIRED"
        return "AUTO_CLEAR"

    @staticmethod
    def _suggest_reviewers(change: ChangeRequest) -> tuple[str, ...]:
        roles = ["operator"]
        if change.change_type.value in ("iam_policy", "terraform_plan"):
            roles.append("security_reviewer")
        if change.is_production_target:
            roles.append("approver")
        return tuple(dict.fromkeys(roles))
