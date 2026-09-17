from __future__ import annotations

import uuid

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.cab_ticket import CabTicket
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.enums.actor_role import ActorRole
from src.domain.enums.change_type import ChangeType


def build_cab_ticket(
    change: ChangeRequest, risk: RiskAssessment, ai: AIAssessment | None
) -> CabTicket:
    evidence: list[str] = [r.description for r in risk.triggered_rules]
    if ai:
        evidence.extend(ai.referenced_evidence)

    roles: list[ActorRole] = [ActorRole.APPROVER]
    if change.change_type in (ChangeType.IAM_POLICY, ChangeType.TERRAFORM_PLAN):
        roles.append(ActorRole.SECURITY_REVIEWER)
    if ai:
        for role_name in ai.recommended_reviewer_roles:
            try:
                role = ActorRole(role_name)
            except ValueError:
                continue
            if role not in roles:
                roles.append(role)

    executive_summary = (
        ai.cab_executive_brief
        if ai
        else f"{change.change_type.value} change to {change.repository}@{change.branch} "
        f"targeting {change.environment_target.value}, risk level {risk.level.label}."
    )

    return CabTicket(
        ticket_id=uuid.uuid4().hex,
        change_id=change.change_id,
        executive_summary=executive_summary,
        business_impact=(
            f"Affects {change.dependency_count} dependent service(s); "
            f"blast radius: {risk.blast_radius_description}"
        ),
        technical_impact=(
            f"{change.changed_file_count} file(s) changed; triggered controls: "
            f"{', '.join(risk.rule_ids) or 'none'}."
        ),
        risk_level=risk.level.label,
        triggered_controls=risk.rule_ids,
        evidence=tuple(dict.fromkeys(evidence)),
        rollback_ready=change.has_rollback_plan,
        maintenance_window_ready=bool(
            change.planned_maintenance_window and change.planned_maintenance_window.is_defined
        ),
        dependencies=change.service_dependencies,
        required_approver_roles=tuple(roles),
        submitted_by=change.submitted_by or change.author,
        created_at=change.submitted_at,
    )
