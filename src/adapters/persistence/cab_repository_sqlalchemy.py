from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.adapters.persistence.mappers import cab_ticket_to_orm, orm_to_cab_ticket
from src.adapters.persistence.models import CabTicketORM
from src.domain.entities.cab_ticket import CabTicket
from src.ports.cab_repository import CabTicketNotFoundError


class SqlAlchemyCabRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_ticket(self, ticket: CabTicket) -> CabTicket:
        orm = cab_ticket_to_orm(ticket)
        self._session.add(orm)
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_cab_ticket(orm)

    def get_ticket(self, ticket_id: str) -> CabTicket:
        orm = self._session.get(CabTicketORM, ticket_id)
        if orm is None:
            raise CabTicketNotFoundError(ticket_id)
        return orm_to_cab_ticket(orm)

    def get_ticket_for_change(self, change_id: str) -> CabTicket | None:
        orm = self._session.execute(
            select(CabTicketORM).where(CabTicketORM.change_id == change_id)
        ).scalar_one_or_none()
        return orm_to_cab_ticket(orm) if orm else None

    def record_decision(
        self, ticket_id: str, *, decision: str, rationale: str, decided_by: str, decided_role: str
    ) -> CabTicket:
        orm = self._session.get(CabTicketORM, ticket_id)
        if orm is None:
            raise CabTicketNotFoundError(ticket_id)
        orm.decision = decision
        orm.decision_rationale = rationale
        orm.decided_by = decided_by
        orm.decided_role = decided_role
        orm.decided_at = datetime.now(UTC)
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_cab_ticket(orm)

    def list_queue(self, limit: int = 50, offset: int = 0) -> tuple[list[CabTicket], int]:
        stmt = select(CabTicketORM).where(CabTicketORM.decision.is_(None))
        count_stmt = select(func.count()).select_from(CabTicketORM).where(CabTicketORM.decision.is_(None))
        total = self._session.execute(count_stmt).scalar_one()
        rows = (
            self._session.execute(
                stmt.order_by(CabTicketORM.created_at.asc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        return [orm_to_cab_ticket(r) for r in rows], total
