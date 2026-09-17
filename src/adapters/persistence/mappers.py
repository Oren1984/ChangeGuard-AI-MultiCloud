"""Bidirectional mapping between pure domain entities and SQLAlchemy ORM
rows. Keeping this in one place means the domain layer never has to know
SQLAlchemy exists.
"""

from __future__ import annotations

from src.adapters.persistence.models import (
    AIAssessmentORM,
    CabTicketORM,
    ChangeORM,
    GateResultORM,
    RiskAssessmentORM,
    RoutingDecisionORM,
)
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.cab_ticket import CabTicket
from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import ChangeRequest, MaintenanceWindow, TerraformPlanEvidence
from src.domain.entities.gate_result import GatePipelineResult, GateResult
from src.domain.entities.risk_assessment import RiskAssessment, TriggeredRule
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.actor_role import ActorRole
from src.domain.enums.change_state import ChangeState
from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment
from src.domain.enums.gate_name import GateName, GateStatus
from src.domain.enums.risk_level import RiskLevel


def change_request_to_orm(change: ChangeRequest, state: ChangeState) -> ChangeORM:
    return ChangeORM(
        change_id=change.change_id,
        repository=change.repository,
        branch=change.branch,
        commit_sha=change.commit_sha,
        author=change.author,
        change_type=change.change_type.value,
        changed_files=list(change.changed_files),
        diff=change.diff,
        terraform_plan=_terraform_plan_to_dict(change.terraform_plan),
        migration_statements=list(change.migration_statements),
        linked_work_item=change.linked_work_item,
        maintenance_window_starts_at=change.planned_maintenance_window.starts_at
        if change.planned_maintenance_window
        else None,
        maintenance_window_ends_at=change.planned_maintenance_window.ends_at
        if change.planned_maintenance_window
        else None,
        has_rollback_plan=change.has_rollback_plan,
        rollback_plan_description=change.rollback_plan_description,
        service_dependencies=list(change.service_dependencies),
        environment_target=change.environment_target.value,
        tests_passed=change.tests_passed,
        submitted_by=change.submitted_by,
        submitted_at=change.submitted_at,
        change_metadata=dict(change.metadata),
        state=state.value,
    )


def _terraform_plan_to_dict(plan: TerraformPlanEvidence | None) -> dict | None:
    if plan is None:
        return None
    return {
        "resource_changes": [
            {
                "address": rc.address,
                "resource_type": rc.resource_type,
                "actions": list(rc.actions),
                "attributes": rc.attributes,
            }
            for rc in plan.resource_changes
        ],
        "raw_plan_json": plan.raw_plan_json,
    }


def _dict_to_terraform_plan(data: dict | None) -> TerraformPlanEvidence | None:
    if not data:
        return None
    from src.domain.entities.change_request import TerraformResourceChange

    resource_changes = tuple(
        TerraformResourceChange(
            address=rc["address"],
            resource_type=rc["resource_type"],
            actions=tuple(rc["actions"]),
            attributes=rc.get("attributes", {}),
        )
        for rc in data.get("resource_changes", [])
    )
    return TerraformPlanEvidence(resource_changes=resource_changes, raw_plan_json=data.get("raw_plan_json"))


def orm_to_change_request(orm: ChangeORM) -> ChangeRequest:
    window = None
    if orm.maintenance_window_starts_at or orm.maintenance_window_ends_at:
        window = MaintenanceWindow(
            starts_at=orm.maintenance_window_starts_at, ends_at=orm.maintenance_window_ends_at
        )
    return ChangeRequest(
        change_id=orm.change_id,
        repository=orm.repository,
        branch=orm.branch,
        commit_sha=orm.commit_sha,
        author=orm.author,
        change_type=ChangeType(orm.change_type),
        changed_files=tuple(orm.changed_files or []),
        diff=orm.diff,
        terraform_plan=_dict_to_terraform_plan(orm.terraform_plan),
        migration_statements=tuple(orm.migration_statements or []),
        linked_work_item=orm.linked_work_item,
        planned_maintenance_window=window,
        has_rollback_plan=orm.has_rollback_plan,
        rollback_plan_description=orm.rollback_plan_description,
        service_dependencies=tuple(orm.service_dependencies or []),
        environment_target=Environment(orm.environment_target),
        tests_passed=orm.tests_passed,
        submitted_by=orm.submitted_by,
        submitted_at=orm.submitted_at,
        metadata=dict(orm.change_metadata or {}),
    )


def risk_assessment_to_orm(change_id: str, assessment: RiskAssessment) -> RiskAssessmentORM:
    return RiskAssessmentORM(
        change_id=change_id,
        score=assessment.score,
        level=assessment.level.label,
        triggered_rules=[
            {
                "rule_id": r.rule_id,
                "category": r.category,
                "severity": r.severity,
                "description": r.description,
                "evidence": list(r.evidence),
                "required_action": r.required_action,
            }
            for r in assessment.triggered_rules
        ],
        blast_radius=assessment.blast_radius,
        blast_radius_description=assessment.blast_radius_description,
        required_governance_actions=list(assessment.required_governance_actions),
    )


def orm_to_risk_assessment(orm: RiskAssessmentORM) -> RiskAssessment:
    return RiskAssessment(
        score=orm.score,
        level=RiskLevel[orm.level],
        triggered_rules=tuple(
            TriggeredRule(
                rule_id=r["rule_id"],
                category=r["category"],
                severity=r["severity"],
                description=r["description"],
                evidence=tuple(r.get("evidence", [])),
                required_action=r.get("required_action"),
            )
            for r in (orm.triggered_rules or [])
        ),
        blast_radius=orm.blast_radius,
        blast_radius_description=orm.blast_radius_description,
        required_governance_actions=tuple(orm.required_governance_actions or []),
    )


def ai_assessment_to_orm(change_id: str, assessment: AIAssessment, *, secondary: bool) -> AIAssessmentORM:
    return AIAssessmentORM(
        change_id=change_id,
        is_secondary=secondary,
        provider_name=assessment.provider_name,
        summary=assessment.summary,
        impact_map=list(assessment.impact_map),
        dependency_concerns=list(assessment.dependency_concerns),
        rollback_considerations=list(assessment.rollback_considerations),
        cab_executive_brief=assessment.cab_executive_brief,
        recommended_reviewer_roles=list(assessment.recommended_reviewer_roles),
        referenced_evidence=list(assessment.referenced_evidence),
        recommended_route=assessment.recommended_route,
        suggested_risk_level=assessment.suggested_risk_level.label,
        confidence=assessment.confidence,
        raw_response=dict(assessment.raw_response),
    )


def orm_to_ai_assessment(orm: AIAssessmentORM) -> AIAssessment:
    return AIAssessment(
        provider_name=orm.provider_name,
        summary=orm.summary,
        impact_map=tuple(orm.impact_map or []),
        dependency_concerns=tuple(orm.dependency_concerns or []),
        rollback_considerations=tuple(orm.rollback_considerations or []),
        cab_executive_brief=orm.cab_executive_brief,
        recommended_reviewer_roles=tuple(orm.recommended_reviewer_roles or []),
        referenced_evidence=tuple(orm.referenced_evidence or []),
        recommended_route=orm.recommended_route,
        suggested_risk_level=RiskLevel[orm.suggested_risk_level],
        confidence=orm.confidence,
        raw_response=dict(orm.raw_response or {}),
    )


def gate_result_to_orm(change_id: str, result: GateResult) -> GateResultORM:
    return GateResultORM(
        change_id=change_id,
        gate=result.gate.value,
        status=result.status.value,
        reason=result.reason,
        details=dict(result.details),
    )


def orm_list_to_gate_pipeline(rows: list[GateResultORM]) -> GatePipelineResult | None:
    if not rows:
        return None
    return GatePipelineResult(
        results=tuple(
            GateResult(
                gate=GateName(r.gate),
                status=GateStatus(r.status),
                reason=r.reason,
                details=dict(r.details or {}),
            )
            for r in rows
        )
    )


def routing_decision_to_orm(change_id: str, decision: RoutingDecision) -> RoutingDecisionORM:
    return RoutingDecisionORM(
        change_id=change_id,
        decision=decision.decision.value,
        reasons=list(decision.reasons),
        policy_ids=list(decision.policy_ids),
    )


def orm_to_routing_decision(orm: RoutingDecisionORM) -> RoutingDecision:
    from src.domain.enums.decision import Decision

    return RoutingDecision(
        decision=Decision(orm.decision),
        reasons=tuple(orm.reasons or []),
        policy_ids=tuple(orm.policy_ids or []),
    )


def cab_ticket_to_orm(ticket: CabTicket) -> CabTicketORM:
    return CabTicketORM(
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


def orm_to_cab_ticket(orm: CabTicketORM) -> CabTicket:
    return CabTicket(
        ticket_id=orm.ticket_id,
        change_id=orm.change_id,
        executive_summary=orm.executive_summary,
        business_impact=orm.business_impact,
        technical_impact=orm.technical_impact,
        risk_level=orm.risk_level,
        triggered_controls=tuple(orm.triggered_controls or []),
        evidence=tuple(orm.evidence or []),
        rollback_ready=orm.rollback_ready,
        maintenance_window_ready=orm.maintenance_window_ready,
        dependencies=tuple(orm.dependencies or []),
        required_approver_roles=tuple(ActorRole(r) for r in (orm.required_approver_roles or [])),
        submitted_by=orm.submitted_by,
        created_at=orm.created_at,
        decision=orm.decision,
        decision_rationale=orm.decision_rationale,
        decided_by=orm.decided_by,
        decided_role=ActorRole(orm.decided_role) if orm.decided_role else None,
        decided_at=orm.decided_at,
    )


def orm_to_change_record(orm: ChangeORM) -> ChangeRecord:
    latest_risk = orm.risk_assessments[-1] if orm.risk_assessments else None
    primary_ai = next((a for a in orm.ai_assessments if not a.is_secondary), None)
    secondary_ai = next((a for a in orm.ai_assessments if a.is_secondary), None)
    latest_routing = orm.routing_decisions[-1] if orm.routing_decisions else None

    return ChangeRecord(
        change=orm_to_change_request(orm),
        state=ChangeState(orm.state),
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        risk_assessment=orm_to_risk_assessment(latest_risk) if latest_risk else None,
        ai_assessment=orm_to_ai_assessment(primary_ai) if primary_ai else None,
        secondary_ai_assessment=orm_to_ai_assessment(secondary_ai) if secondary_ai else None,
        gate_result=orm_list_to_gate_pipeline(list(orm.gate_results)),
        routing_decision=orm_to_routing_decision(latest_routing) if latest_routing else None,
        cab_ticket=orm_to_cab_ticket(orm.cab_ticket) if orm.cab_ticket else None,
    )
