from __future__ import annotations

from sqlalchemy.orm import Session

from src.adapters.persistence.models import KillSwitchStateORM
from src.domain.policies.kill_switch_policy import KillSwitchState


class SqlAlchemyKillSwitchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_state(self) -> KillSwitchState:
        orm = self._session.get(KillSwitchStateORM, 1)
        if orm is None:
            return KillSwitchState(active=False)
        return KillSwitchState(active=orm.active, activated_by=orm.activated_by, reason=orm.reason)

    def set_state(self, state: KillSwitchState) -> KillSwitchState:
        orm = self._session.get(KillSwitchStateORM, 1)
        if orm is None:
            orm = KillSwitchStateORM(id=1)
            self._session.add(orm)
        orm.active = state.active
        orm.activated_by = state.activated_by
        orm.reason = state.reason
        self._session.commit()
        return state
