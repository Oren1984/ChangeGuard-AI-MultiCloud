from __future__ import annotations

from pydantic import ValidationError

from src.application.evaluation.schemas import AIAssessmentSchema
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.gate_result import GateResult
from src.domain.enums.gate_name import GateName, GateStatus


def run_schema_gate(assessment: AIAssessment) -> GateResult:
    payload = {
        "provider_name": assessment.provider_name,
        "summary": assessment.summary,
        "impact_map": list(assessment.impact_map),
        "dependency_concerns": list(assessment.dependency_concerns),
        "rollback_considerations": list(assessment.rollback_considerations),
        "cab_executive_brief": assessment.cab_executive_brief,
        "recommended_reviewer_roles": list(assessment.recommended_reviewer_roles),
        "referenced_evidence": list(assessment.referenced_evidence),
        "recommended_route": assessment.recommended_route,
        "suggested_risk_level": assessment.suggested_risk_level.label,
        "confidence": assessment.confidence,
    }
    try:
        AIAssessmentSchema.model_validate(payload)
    except ValidationError as exc:
        return GateResult(
            gate=GateName.SCHEMA,
            status=GateStatus.FAILED,
            reason="AI response failed strict schema validation.",
            details={"errors": exc.errors(include_url=False)},
        )
    return GateResult(
        gate=GateName.SCHEMA,
        status=GateStatus.PASSED,
        reason="AI response conforms to the strict output schema.",
    )
