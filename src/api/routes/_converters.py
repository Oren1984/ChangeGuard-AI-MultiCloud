from __future__ import annotations

from src.api.schemas.change_schemas import (
    AIAssessmentResponse,
    CabTicketResponse,
    ChangeDetailResponse,
    ChangeSubmitRequest,
    ChangeSummaryResponse,
    GateResultResponse,
    RiskAssessmentResponse,
    RoutingDecisionResponse,
)
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.cab_ticket import CabTicket
from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import (
    ChangeRequest,
    MaintenanceWindow,
    TerraformPlanEvidence,
    TerraformResourceChange,
)
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment


def request_to_change_request(req: ChangeSubmitRequest) -> ChangeRequest:
    terraform_plan = None
    if req.terraform_plan:
        terraform_plan = TerraformPlanEvidence(
            resource_changes=tuple(
                TerraformResourceChange(
                    address=rc.address,
                    resource_type=rc.resource_type,
                    actions=tuple(rc.actions),
                    attributes=rc.attributes,
                )
                for rc in req.terraform_plan.resource_changes
            ),
            raw_plan_json=req.terraform_plan.raw_plan_json,
        )

    window = None
    if req.planned_maintenance_window:
        window = MaintenanceWindow(
            starts_at=req.planned_maintenance_window.starts_at,
            ends_at=req.planned_maintenance_window.ends_at,
        )

    return ChangeRequest(
        change_id=req.change_id,
        repository=req.repository,
        branch=req.branch,
        commit_sha=req.commit_sha,
        author=req.author,
        change_type=ChangeType(req.change_type),
        changed_files=tuple(req.changed_files),
        diff=req.diff,
        terraform_plan=terraform_plan,
        migration_statements=tuple(req.migration_statements),
        linked_work_item=req.linked_work_item,
        planned_maintenance_window=window,
        has_rollback_plan=req.has_rollback_plan,
        rollback_plan_description=req.rollback_plan_description,
        service_dependencies=tuple(req.service_dependencies),
        environment_target=Environment(req.environment_target),
        tests_passed=req.tests_passed,
        submitted_by=req.submitted_by or req.author,
        metadata=req.metadata,
    )


def _risk_to_response(risk: RiskAssessment) -> RiskAssessmentResponse:
    return RiskAssessmentResponse(
        score=risk.score,
        level=risk.level.label,
        triggered_rules=[
            {
                "rule_id": r.rule_id,
                "category": r.category,
                "severity": r.severity,
                "description": r.description,
                "evidence": list(r.evidence),
                "required_action": r.required_action,
            }
            for r in risk.triggered_rules
        ],
        blast_radius=risk.blast_radius,
        blast_radius_description=risk.blast_radius_description,
        required_governance_actions=list(risk.required_governance_actions),
    )


def _ai_to_response(ai: AIAssessment) -> AIAssessmentResponse:
    return AIAssessmentResponse(
        provider_name=ai.provider_name,
        summary=ai.summary,
        impact_map=list(ai.impact_map),
        dependency_concerns=list(ai.dependency_concerns),
        rollback_considerations=list(ai.rollback_considerations),
        cab_executive_brief=ai.cab_executive_brief,
        recommended_reviewer_roles=list(ai.recommended_reviewer_roles),
        referenced_evidence=list(ai.referenced_evidence),
        recommended_route=ai.recommended_route,
        suggested_risk_level=ai.suggested_risk_level.label,
        confidence=ai.confidence,
    )


def _cab_to_response(ticket: CabTicket) -> CabTicketResponse:
    return CabTicketResponse(
        ticket_id=ticket.ticket_id,
        change_id=ticket.change_id,
        executive_summary=ticket.executive_summary,
        business_impact=ticket.business_impact,
        technical_impact=ticket.technical_impact,
        risk_level=ticket.risk_level,
        triggered_controls=list(ticket.triggered_controls),
        evidence=list(ticket.evidence),
        rollback_ready=ticket.rollback_ready,
        maintenance_window_ready=ticket.maintenance_window_ready,
        dependencies=list(ticket.dependencies),
        required_approver_roles=[r.value for r in ticket.required_approver_roles],
        submitted_by=ticket.submitted_by,
        created_at=ticket.created_at,
        decision=ticket.decision,
        decision_rationale=ticket.decision_rationale,
        decided_by=ticket.decided_by,
        decided_role=ticket.decided_role.value if ticket.decided_role else None,
        decided_at=ticket.decided_at,
    )


def record_to_summary(record: ChangeRecord) -> ChangeSummaryResponse:
    return ChangeSummaryResponse(
        change_id=record.change.change_id,
        repository=record.change.repository,
        branch=record.change.branch,
        change_type=record.change.change_type.value,
        environment_target=record.change.environment_target.value,
        state=record.state.value,
        risk_level=record.risk_assessment.level.label if record.risk_assessment else None,
        decision=record.routing_decision.decision.value if record.routing_decision else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def record_to_detail(record: ChangeRecord) -> ChangeDetailResponse:
    return ChangeDetailResponse(
        change_id=record.change.change_id,
        repository=record.change.repository,
        branch=record.change.branch,
        commit_sha=record.change.commit_sha,
        author=record.change.author,
        change_type=record.change.change_type.value,
        changed_files=list(record.change.changed_files),
        environment_target=record.change.environment_target.value,
        state=record.state.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        risk_assessment=_risk_to_response(record.risk_assessment) if record.risk_assessment else None,
        ai_assessment=_ai_to_response(record.ai_assessment) if record.ai_assessment else None,
        secondary_ai_assessment=(
            _ai_to_response(record.secondary_ai_assessment) if record.secondary_ai_assessment else None
        ),
        gate_results=[
            GateResultResponse(gate=r.gate.value, status=r.status.value, reason=r.reason, details=r.details)
            for r in (record.gate_result.results if record.gate_result else [])
        ],
        routing_decision=(
            RoutingDecisionResponse(
                decision=record.routing_decision.decision.value,
                reasons=list(record.routing_decision.reasons),
                policy_ids=list(record.routing_decision.policy_ids),
            )
            if record.routing_decision
            else None
        ),
        cab_ticket=_cab_to_response(record.cab_ticket) if record.cab_ticket else None,
    )
