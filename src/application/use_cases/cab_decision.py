from __future__ import annotations

from src.domain.entities.change_record import ChangeRecord
from src.domain.enums.actor_role import ActorRole
from src.domain.enums.change_state import ChangeState
from src.domain.policies.separation_of_duties import can_decide_cab_ticket
from src.domain.state_machine.transitions import validate_transition
from src.ports.audit_repository import AuditRepository
from src.ports.cab_repository import CabRepository
from src.ports.change_repository import ChangeRepository


class SeparationOfDutiesViolationError(Exception):
    pass


class NoCabTicketError(Exception):
    pass


class CabDecisionUseCase:
    """Records a CAB approve/reject decision and cascades the resulting
    state transition. A submitter may never decide their own change
    (separation of duties, enforced here — not just at the UI layer)."""

    def __init__(
        self, change_repo: ChangeRepository, cab_repo: CabRepository, audit_repo: AuditRepository
    ) -> None:
        self._change_repo = change_repo
        self._cab_repo = cab_repo
        self._audit_repo = audit_repo

    def execute(
        self,
        change_id: str,
        *,
        approve: bool,
        rationale: str,
        actor: str,
        actor_role: ActorRole,
    ) -> ChangeRecord:
        ticket = self._cab_repo.get_ticket_for_change(change_id)
        if ticket is None:
            raise NoCabTicketError(change_id)

        allowed, reason = can_decide_cab_ticket(ticket, actor, actor_role)
        if not allowed:
            raise SeparationOfDutiesViolationError(reason)

        record = self._change_repo.get(change_id)
        validate_transition(
            record.state, ChangeState.CAB_APPROVED if approve else ChangeState.CAB_REJECTED
        )

        decision = "APPROVED" if approve else "REJECTED"
        self._cab_repo.record_decision(
            ticket.ticket_id,
            decision=decision,
            rationale=rationale,
            decided_by=actor,
            decided_role=actor_role.value,
        )

        intermediate_state = ChangeState.CAB_APPROVED if approve else ChangeState.CAB_REJECTED
        self._change_repo.update_state(change_id, intermediate_state)
        self._audit_repo.append(
            actor=actor,
            actor_role=actor_role.value,
            action=f"CAB_{decision}",
            entity_id=change_id,
            payload={"ticket_id": ticket.ticket_id, "rationale": rationale},
        )

        final_state = ChangeState.READY_TO_SHIP if approve else ChangeState.BLOCKED
        validate_transition(intermediate_state, final_state)
        self._change_repo.update_state(change_id, final_state)
        self._audit_repo.append(
            actor=actor,
            actor_role=actor_role.value,
            action="STATE_TRANSITION",
            entity_id=change_id,
            payload={"from": intermediate_state.value, "to": final_state.value},
        )

        return self._change_repo.get(change_id)
