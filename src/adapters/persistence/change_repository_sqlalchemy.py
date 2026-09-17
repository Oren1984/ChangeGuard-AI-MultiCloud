from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.adapters.persistence.mappers import (
    ai_assessment_to_orm,
    change_request_to_orm,
    gate_result_to_orm,
    orm_to_change_record,
    risk_assessment_to_orm,
    routing_decision_to_orm,
)
from src.adapters.persistence.models import ChangeORM
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GatePipelineResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.change_state import ChangeState
from src.ports.change_repository import ChangeNotFoundError, DuplicateChangeError


class SqlAlchemyChangeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, change: ChangeRequest) -> ChangeRecord:
        orm = change_request_to_orm(change, ChangeState.PROPOSED)
        self._session.add(orm)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateChangeError(f"change_id '{change.change_id}' already exists") from exc
        self._session.refresh(orm)
        return orm_to_change_record(orm)

    def get(self, change_id: str) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        return orm_to_change_record(orm)

    def exists(self, change_id: str) -> bool:
        return self._session.get(ChangeORM, change_id) is not None

    def list(
        self, *, state: ChangeState | None = None, limit: int = 50, offset: int = 0
    ) -> tuple[list[ChangeRecord], int]:
        stmt = select(ChangeORM)
        count_stmt = select(func.count()).select_from(ChangeORM)
        if state is not None:
            stmt = stmt.where(ChangeORM.state == state.value)
            count_stmt = count_stmt.where(ChangeORM.state == state.value)

        total = self._session.execute(count_stmt).scalar_one()
        rows = (
            self._session.execute(
                stmt.order_by(ChangeORM.created_at.desc()).limit(limit).offset(offset)
            )
            .scalars()
            .all()
        )
        return [orm_to_change_record(r) for r in rows], total

    def update_state(self, change_id: str, new_state: ChangeState) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        orm.state = new_state.value
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_change_record(orm)

    def attach_risk_assessment(self, change_id: str, assessment: RiskAssessment) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        self._session.add(risk_assessment_to_orm(change_id, assessment))
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_change_record(orm)

    def attach_ai_assessment(
        self, change_id: str, assessment: AIAssessment, *, secondary: bool = False
    ) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        self._session.add(ai_assessment_to_orm(change_id, assessment, secondary=secondary))
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_change_record(orm)

    def attach_gate_result(self, change_id: str, result: GatePipelineResult) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        for gate_result in result.results:
            self._session.add(gate_result_to_orm(change_id, gate_result))
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_change_record(orm)

    def attach_routing_decision(self, change_id: str, decision: RoutingDecision) -> ChangeRecord:
        orm = self._session.get(ChangeORM, change_id)
        if orm is None:
            raise ChangeNotFoundError(change_id)
        self._session.add(routing_decision_to_orm(change_id, decision))
        self._session.commit()
        self._session.refresh(orm)
        return orm_to_change_record(orm)
