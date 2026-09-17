from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.enums.actor_role import ActorRole


@dataclass(frozen=True, slots=True)
class CabTicket:
    ticket_id: str
    change_id: str
    executive_summary: str
    business_impact: str
    technical_impact: str
    risk_level: str
    triggered_controls: tuple[str, ...]
    evidence: tuple[str, ...]
    rollback_ready: bool
    maintenance_window_ready: bool
    dependencies: tuple[str, ...]
    required_approver_roles: tuple[ActorRole, ...]
    submitted_by: str
    created_at: datetime
    decision: str | None = None  # "APPROVED" | "REJECTED" | None
    decision_rationale: str | None = None
    decided_by: str | None = None
    decided_role: ActorRole | None = None
    decided_at: datetime | None = None

    def can_be_decided_by(self, actor: str, role: ActorRole) -> tuple[bool, str]:
        """Separation-of-duties check: the submitter may not decide their own ticket."""
        if actor == self.submitted_by:
            return False, "submitter cannot approve or reject their own change"
        from src.domain.enums.actor_role import CAB_DECISION_ROLES

        if role not in CAB_DECISION_ROLES:
            return False, f"role '{role}' is not authorized to record a CAB decision"
        return True, ""
