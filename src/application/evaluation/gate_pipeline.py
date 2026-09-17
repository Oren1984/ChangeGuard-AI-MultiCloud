from __future__ import annotations

from src.application.evaluation.confidence_gate import ConfidenceThresholds, run_confidence_gate
from src.application.evaluation.consistency_gate import run_consistency_gate
from src.application.evaluation.grounding_gate import run_grounding_gate
from src.application.evaluation.safety_gate import run_safety_gate
from src.application.evaluation.schema_gate import run_schema_gate
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GatePipelineResult, GateResult
from src.domain.enums.gate_name import GateName, GateStatus


def _skipped(gate: GateName, reason: str) -> GateResult:
    return GateResult(gate=gate, status=GateStatus.SKIPPED, reason=reason)


def run_gate_pipeline(
    *,
    primary: AIAssessment,
    change: ChangeRequest,
    secondary: AIAssessment | None = None,
    confidence_thresholds: ConfidenceThresholds = ConfidenceThresholds(),
) -> GatePipelineResult:
    """Runs all five mandatory assurance gates, in order, and persists every
    result — including SKIPPED ones — so the audit trail always shows what
    ran and why. Schema failure short-circuits gates 2-4 because semantic
    checks on a structurally invalid response are meaningless; it does not
    skip Gate 5, since consistency is a structural comparison independent of
    either individual response's schema validity.
    """
    schema_result = run_schema_gate(primary)

    if schema_result.status == GateStatus.FAILED:
        grounding_result = _skipped(GateName.GROUNDING, "skipped: Gate 1 (schema) failed upstream")
        confidence_result = _skipped(GateName.CONFIDENCE, "skipped: Gate 1 (schema) failed upstream")
        safety_result = _skipped(GateName.SAFETY, "skipped: Gate 1 (schema) failed upstream")
    else:
        grounding_result = run_grounding_gate(primary, change)
        confidence_result = run_confidence_gate(primary, confidence_thresholds)
        safety_result = run_safety_gate(primary)

    if secondary is None:
        consistency_result = _skipped(GateName.CONSISTENCY, "skipped: no secondary AI opinion was provided")
    else:
        consistency_result = run_consistency_gate(primary, secondary)

    return GatePipelineResult(
        results=(
            schema_result,
            grounding_result,
            confidence_result,
            safety_result,
            consistency_result,
        )
    )
