from __future__ import annotations

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.gate_result import GateResult
from src.domain.enums.gate_name import GateName, GateStatus

# Categorical blocklist: any of these appearing in AI-generated text is an
# automatic hard failure, independent of confidence or risk level.
_FORBIDDEN_PATTERNS: tuple[str, ...] = (
    "terraform destroy",
    "disable audit",
    "disable logging",
    "suppress logging",
    "bypass review",
    "bypass approval",
    "force deploy",
    "force the deployment",
    "skip tests",
    "ignore failed tests",
    "ignore failing tests",
    "ignore the policy",
    "drop database",
    "delete production",
    "disable security",
    "rm -rf",
)


def run_safety_gate(assessment: AIAssessment) -> GateResult:
    haystack = "\n".join(
        [
            assessment.summary,
            assessment.cab_executive_brief,
            *assessment.rollback_considerations,
            *assessment.dependency_concerns,
            *assessment.impact_map,
        ]
    ).lower()

    hits = [pattern for pattern in _FORBIDDEN_PATTERNS if pattern in haystack]
    if hits:
        return GateResult(
            gate=GateName.SAFETY,
            status=GateStatus.FAILED,
            reason="AI response recommends a categorically unsafe action.",
            details={"matched_patterns": hits},
        )

    return GateResult(
        gate=GateName.SAFETY,
        status=GateStatus.PASSED,
        reason="No unsafe recommendations detected in the AI response.",
    )
