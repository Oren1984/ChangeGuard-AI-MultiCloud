"""In-memory fakes satisfying the repository Protocols, used by assurance
and use-case tests that exercise orchestration logic without a database."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.audit_record import AuditRecord
from src.domain.entities.cab_ticket import CabTicket
from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GatePipelineResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.change_state import ChangeState
from src.domain.policies.audit_chain import (
    GENESIS_HASH,
    ChainLink,
    canonicalize_payload,
    compute_hash,
    verify_chain,
)
from src.domain.policies.kill_switch_policy import KillSwitchState
from src.ports.audit_repository import AuditPersistenceError
from src.ports.cab_repository import CabTicketNotFoundError
from src.ports.change_repository import ChangeNotFoundError, DuplicateChangeError


class FakeChangeRepository:
    def __init__(self) -> None:
        self._records: dict[str, ChangeRecord] = {}
        # Mirrors the SQL adapter's live JOIN of cab_tickets onto changes:
        # set by whoever wires up the fakes (see conftest), so a change
        # record always reflects its ticket regardless of write order.
        self.cab_repo: FakeCabRepository | None = None

    def create(self, change: ChangeRequest) -> ChangeRecord:
        if change.change_id in self._records:
            raise DuplicateChangeError(change.change_id)
        now = datetime.now(UTC)
        record = ChangeRecord(change=change, state=ChangeState.PROPOSED, created_at=now, updated_at=now)
        self._records[change.change_id] = record
        return record

    def _materialize(self, record: ChangeRecord) -> ChangeRecord:
        if self.cab_repo is None:
            return record
        ticket = self.cab_repo.get_ticket_for_change(record.change.change_id)
        return replace(record, cab_ticket=ticket) if ticket else record

    def get(self, change_id: str) -> ChangeRecord:
        try:
            return self._materialize(self._records[change_id])
        except KeyError as exc:
            raise ChangeNotFoundError(change_id) from exc

    def exists(self, change_id: str) -> bool:
        return change_id in self._records

    def list(self, *, state=None, limit: int = 50, offset: int = 0):
        items = [self._materialize(r) for r in self._records.values()]
        if state is not None:
            items = [r for r in items if r.state == state]
        return items[offset : offset + limit], len(items)

    def update_state(self, change_id: str, new_state: ChangeState) -> ChangeRecord:
        record = self.get(change_id)
        updated = replace(record, state=new_state, updated_at=datetime.now(UTC))
        self._records[change_id] = updated
        return updated

    def attach_risk_assessment(self, change_id: str, assessment: RiskAssessment) -> ChangeRecord:
        record = self.get(change_id)
        updated = replace(record, risk_assessment=assessment)
        self._records[change_id] = updated
        return updated

    def attach_ai_assessment(
        self, change_id: str, assessment: AIAssessment, *, secondary: bool = False
    ) -> ChangeRecord:
        record = self.get(change_id)
        if secondary:
            updated = replace(record, secondary_ai_assessment=assessment)
        else:
            updated = replace(record, ai_assessment=assessment)
        self._records[change_id] = updated
        return updated

    def attach_gate_result(self, change_id: str, result: GatePipelineResult) -> ChangeRecord:
        record = self.get(change_id)
        updated = replace(record, gate_result=result)
        self._records[change_id] = updated
        return updated

    def attach_routing_decision(self, change_id: str, decision: RoutingDecision) -> ChangeRecord:
        record = self.get(change_id)
        updated = replace(record, routing_decision=decision)
        self._records[change_id] = updated
        return updated


class FakeCabRepository:
    def __init__(self) -> None:
        self._tickets: dict[str, CabTicket] = {}
        self._by_change: dict[str, str] = {}

    def create_ticket(self, ticket: CabTicket) -> CabTicket:
        self._tickets[ticket.ticket_id] = ticket
        self._by_change[ticket.change_id] = ticket.ticket_id
        return ticket

    def get_ticket(self, ticket_id: str) -> CabTicket:
        try:
            return self._tickets[ticket_id]
        except KeyError as exc:
            raise CabTicketNotFoundError(ticket_id) from exc

    def get_ticket_for_change(self, change_id: str) -> CabTicket | None:
        ticket_id = self._by_change.get(change_id)
        return self._tickets.get(ticket_id) if ticket_id else None

    def record_decision(
        self, ticket_id: str, *, decision: str, rationale: str, decided_by: str, decided_role: str
    ) -> CabTicket:
        from src.domain.enums.actor_role import ActorRole

        ticket = self.get_ticket(ticket_id)
        updated = replace(
            ticket,
            decision=decision,
            decision_rationale=rationale,
            decided_by=decided_by,
            decided_role=ActorRole(decided_role),
            decided_at=datetime.now(UTC),
        )
        self._tickets[ticket_id] = updated
        return updated

    def list_queue(self, limit: int = 50, offset: int = 0):
        pending = [t for t in self._tickets.values() if t.decision is None]
        return pending[offset : offset + limit], len(pending)


class FakeAuditRepository:
    """Same hash-chain semantics as the SQL implementation, in memory."""

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self.fail_next = False

    def append(
        self, *, actor: str, actor_role: str, action: str, entity_id: str, payload: dict
    ) -> AuditRecord:
        if self.fail_next:
            self.fail_next = False
            raise AuditPersistenceError("simulated audit persistence failure")

        previous_hash = self._records[-1].current_hash if self._records else GENESIS_HASH
        sequence = len(self._records) + 1
        timestamp = datetime.now(UTC)
        canonical = canonicalize_payload(
            {
                "sequence": sequence,
                "timestamp": timestamp.isoformat(),
                "actor": actor,
                "actor_role": actor_role,
                "action": action,
                "entity_id": entity_id,
                "payload": payload,
            }
        )
        current_hash = compute_hash(previous_hash, canonical)
        record = AuditRecord(
            sequence=sequence,
            timestamp=timestamp,
            actor=actor,
            actor_role=actor_role,
            action=action,
            entity_id=entity_id,
            previous_hash=previous_hash,
            canonical_payload=canonical,
            current_hash=current_hash,
        )
        self._records.append(record)
        return record

    def verify_chain(self):
        links = [
            ChainLink(r.sequence, r.previous_hash, r.canonical_payload, r.current_hash) for r in self._records
        ]
        return verify_chain(links)

    def list_recent(self, limit: int = 50) -> list[AuditRecord]:
        return list(reversed(self._records))[:limit]

    def list_for_entity(self, entity_id: str) -> list[AuditRecord]:
        return [r for r in self._records if r.entity_id == entity_id]


class FakeKillSwitchRepository:
    def __init__(self, initial_active: bool = False) -> None:
        self._state = KillSwitchState(active=initial_active)

    def get_state(self) -> KillSwitchState:
        return self._state

    def set_state(self, state: KillSwitchState) -> KillSwitchState:
        self._state = state
        return state
