"""Pure, infrastructure-independent decision router.

This function is the single point that turns evaluation evidence into one
of the three governance outcomes. It intentionally never reads
`AIAssessment.recommended_route` — the AI's opinion is advisory-only and
surfaced to humans (CAB brief, dashboard), but it structurally cannot
influence the routing decision. Only the deterministic risk engine and the
assurance-gate results can.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.gate_result import GatePipelineResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.decision import Decision
from src.domain.enums.risk_level import RiskLevel

_EVIDENCE_GAP_RULE_IDS = frozenset({"RISK-OPS-001", "RISK-OPS-002", "RISK-DB-003"})


@dataclass(frozen=True, slots=True)
class RoutingContext:
    """Everything the router needs, gathered by the orchestration layer.

    Deliberately a plain, serializable bag of values — not a live object
    graph — so the function stays a pure, exhaustively-unit-testable
    transformation from evidence to decision.
    """

    risk: RiskAssessment
    gates: GatePipelineResult
    kill_switch_active: bool
    allow_critical_cab_exception: bool = False
    critical_cab_exception_requested: bool = False


def route_decision(ctx: RoutingContext) -> RoutingDecision:
    reasons: list[str] = []
    policy_ids: list[str] = []

    # 1. Mandatory deterministic rule violation or CRITICAL risk.
    if ctx.risk.has_mandatory_violation or ctx.risk.level == RiskLevel.CRITICAL:
        exception_applies = ctx.allow_critical_cab_exception and ctx.critical_cab_exception_requested
        if not exception_applies:
            reasons.append("Critical risk or a mandatory deterministic rule was violated.")
            policy_ids.append("POL-CRITICAL-001")
            return RoutingDecision(Decision.HARD_BLOCK, tuple(reasons), tuple(policy_ids))
        reasons.append("Critical risk, routed to CAB under an explicitly configured exception.")
        policy_ids.append("POL-CRITICAL-002")
        return RoutingDecision(Decision.CAB_REVIEW_REQUIRED, tuple(reasons), tuple(policy_ids))

    # 2. Any failed assurance gate is an automatic hard block (fail closed).
    if ctx.gates.any_failed:
        failed = [r.gate.value for r in ctx.gates.results if r.failed]
        reasons.append(f"AI assurance gate(s) failed: {', '.join(failed)}.")
        policy_ids.append("POL-GATE-FAIL-001")
        return RoutingDecision(Decision.HARD_BLOCK, tuple(reasons), tuple(policy_ids))

    # 3. HIGH risk always requires CAB review at minimum.
    if ctx.risk.level == RiskLevel.HIGH:
        reasons.append("Deterministic risk level is HIGH; CAB review is mandatory.")
        policy_ids.append("POL-HIGH-001")
        return RoutingDecision(Decision.CAB_REVIEW_REQUIRED, tuple(reasons), tuple(policy_ids))

    # 4. Any gate warning (including AI inconsistency) forces human review.
    if ctx.gates.any_warning:
        warned = [r.gate.value for r in ctx.gates.results if r.status.value == "WARNING"]
        reasons.append(f"AI assurance gate(s) returned a warning: {', '.join(warned)}.")
        policy_ids.append("POL-GATE-WARN-001")
        return RoutingDecision(Decision.CAB_REVIEW_REQUIRED, tuple(reasons), tuple(policy_ids))

    # 5. Required operational evidence (rollback plan / maintenance window)
    #    must exist before LOW/MEDIUM risk can auto-clear.
    if ctx.risk.rule_ids and (set(ctx.risk.rule_ids) & _EVIDENCE_GAP_RULE_IDS):
        reasons.append("Required operational evidence (rollback plan / maintenance window) is missing.")
        policy_ids.append("POL-EVIDENCE-001")
        return RoutingDecision(Decision.CAB_REVIEW_REQUIRED, tuple(reasons), tuple(policy_ids))

    # 6. Kill switch: no AI-assisted change may auto-clear while active.
    if ctx.kill_switch_active:
        reasons.append("AI kill switch is active; auto-clear is disabled and manual review is required.")
        policy_ids.append("POL-KILLSWITCH-001")
        return RoutingDecision(Decision.CAB_REVIEW_REQUIRED, tuple(reasons), tuple(policy_ids))

    # 7. LOW/MEDIUM risk, all gates passed, evidence present, kill switch off.
    reasons.append("Risk is LOW/MEDIUM, all assurance gates passed, and required evidence is present.")
    policy_ids.append("POL-AUTOCLEAR-001")
    return RoutingDecision(Decision.AUTO_CLEAR, tuple(reasons), tuple(policy_ids))
