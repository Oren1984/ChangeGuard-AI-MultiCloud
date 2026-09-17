from __future__ import annotations

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.gate_result import GateResult
from src.domain.enums.gate_name import GateName, GateStatus

CONFIDENCE_DRIFT_THRESHOLD = 0.30


def run_consistency_gate(primary: AIAssessment, secondary: AIAssessment) -> GateResult:
    mismatches: list[str] = []

    if primary.recommended_route != secondary.recommended_route:
        mismatches.append(
            f"recommended_route differs: {primary.recommended_route} vs {secondary.recommended_route}"
        )
    if primary.suggested_risk_level != secondary.suggested_risk_level:
        mismatches.append(
            f"suggested_risk_level differs: {primary.suggested_risk_level.label} "
            f"vs {secondary.suggested_risk_level.label}"
        )
    confidence_delta = abs(primary.confidence - secondary.confidence)
    if confidence_delta > CONFIDENCE_DRIFT_THRESHOLD:
        mismatches.append(f"confidence differs by {confidence_delta:.2f}")

    primary_evidence = set(primary.referenced_evidence)
    secondary_evidence = set(secondary.referenced_evidence)
    if primary_evidence and secondary_evidence:
        overlap = len(primary_evidence & secondary_evidence) / len(primary_evidence | secondary_evidence)
        if overlap < 0.5:
            mismatches.append(f"referenced_evidence overlap is only {overlap:.0%}")

    if mismatches:
        return GateResult(
            gate=GateName.CONSISTENCY,
            status=GateStatus.WARNING,
            reason="Primary and secondary AI opinions materially disagree; mandatory human review required.",
            details={"mismatches": mismatches},
        )

    return GateResult(
        gate=GateName.CONSISTENCY,
        status=GateStatus.PASSED,
        reason="Primary and secondary AI opinions are materially consistent.",
    )
