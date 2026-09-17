from __future__ import annotations

from typing import Protocol

from src.domain.entities.cab_ticket import CabTicket


class CabTicketNotFoundError(Exception):
    pass


class CabRepository(Protocol):
    def create_ticket(self, ticket: CabTicket) -> CabTicket:
        ...

    def get_ticket(self, ticket_id: str) -> CabTicket:
        ...

    def get_ticket_for_change(self, change_id: str) -> CabTicket | None:
        ...

    def record_decision(
        self,
        ticket_id: str,
        *,
        decision: str,
        rationale: str,
        decided_by: str,
        decided_role: str,
    ) -> CabTicket:
        ...

    def list_queue(self, limit: int = 50, offset: int = 0) -> tuple[list[CabTicket], int]:
        ...
