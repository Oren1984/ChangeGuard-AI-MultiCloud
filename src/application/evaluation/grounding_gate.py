from __future__ import annotations

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GateResult
from src.domain.enums.gate_name import GateName, GateStatus


def _known_evidence_set(change: ChangeRequest) -> set[str]:
    known: set[str] = set(change.changed_files)
    known.add(f"repository:{change.repository}")
    known.add(f"branch:{change.branch}")
    if change.terraform_plan:
        known.update(rc.address for rc in change.terraform_plan.resource_changes)
    known.update(f"migration:{s[:60]}" for s in change.migration_statements)
    known.update(change.service_dependencies)
    return known


def run_grounding_gate(assessment: AIAssessment, change: ChangeRequest) -> GateResult:
    if not assessment.referenced_evidence:
        return GateResult(
            gate=GateName.GROUNDING,
            status=GateStatus.WARNING,
            reason="AI response cited no evidence; mandatory human review required.",
        )

    known = _known_evidence_set(change)
    fabricated = [item for item in assessment.referenced_evidence if item not in known]

    if fabricated:
        return GateResult(
            gate=GateName.GROUNDING,
            status=GateStatus.FAILED,
            reason="AI response references evidence not present in the submitted change (fabrication).",
            details={"fabricated_evidence": fabricated},
        )

    return GateResult(
        gate=GateName.GROUNDING,
        status=GateStatus.PASSED,
        reason="Every referenced evidence item is grounded in the submitted change.",
        details={"evidence_count": len(assessment.referenced_evidence)},
    )
