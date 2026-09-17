from __future__ import annotations

from dataclasses import asdict, dataclass

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.gate_result import GateResult
from src.domain.enums.gate_name import GateName, GateStatus


@dataclass(frozen=True, slots=True)
class ConfidenceThresholds:
    approval_threshold: float = 0.70
    hard_floor: float = 0.35


DEFAULT_THRESHOLDS = ConfidenceThresholds()


def run_confidence_gate(
    assessment: AIAssessment, thresholds: ConfidenceThresholds = DEFAULT_THRESHOLDS
) -> GateResult:
    confidence = assessment.confidence
    details = {"confidence": confidence, **asdict(thresholds)}

    if confidence < thresholds.hard_floor:
        return GateResult(
            gate=GateName.CONFIDENCE,
            status=GateStatus.FAILED,
            reason=f"Confidence {confidence:.2f} is below the hard floor {thresholds.hard_floor:.2f}.",
            details=details,
        )
    if confidence < thresholds.approval_threshold:
        return GateResult(
            gate=GateName.CONFIDENCE,
            status=GateStatus.WARNING,
            reason=(
                f"Confidence {confidence:.2f} is in the mandatory-review range "
                f"[{thresholds.hard_floor:.2f}, {thresholds.approval_threshold:.2f})."
            ),
            details=details,
        )
    return GateResult(
        gate=GateName.CONFIDENCE,
        status=GateStatus.PASSED,
        reason=(
            f"Confidence {confidence:.2f} meets the approval threshold "
            f"{thresholds.approval_threshold:.2f}."
        ),
        details=details,
    )
