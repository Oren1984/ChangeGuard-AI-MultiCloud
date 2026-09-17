from __future__ import annotations

from src.domain.entities.cab_ticket import CabTicket
from src.domain.enums.actor_role import CAB_DECISION_ROLES, ActorRole


def can_decide_cab_ticket(ticket: CabTicket, actor: str, role: ActorRole) -> tuple[bool, str]:
    if actor == ticket.submitted_by:
        return False, "submitter cannot approve or reject their own change"
    if role not in CAB_DECISION_ROLES:
        return False, f"role '{role.value}' is not authorized to record a CAB decision"
    return True, ""
