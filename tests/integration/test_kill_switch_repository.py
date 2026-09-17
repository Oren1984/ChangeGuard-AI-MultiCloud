from __future__ import annotations

from src.adapters.persistence.kill_switch_repository_sqlalchemy import SqlAlchemyKillSwitchRepository
from src.domain.policies.kill_switch_policy import KillSwitchState


def test_default_state_when_unset(db_session):
    repo = SqlAlchemyKillSwitchRepository(db_session)
    state = repo.get_state()
    assert state.active is False


def test_set_and_get_round_trips(db_session):
    repo = SqlAlchemyKillSwitchRepository(db_session)
    repo.set_state(KillSwitchState(active=True, activated_by="admin.one", reason="incident"))
    state = repo.get_state()
    assert state.active is True
    assert state.activated_by == "admin.one"
    assert state.reason == "incident"


def test_set_state_is_idempotent_upsert(db_session):
    repo = SqlAlchemyKillSwitchRepository(db_session)
    repo.set_state(KillSwitchState(active=True, activated_by="admin.one", reason="first"))
    repo.set_state(KillSwitchState(active=False, activated_by="admin.two", reason="resolved"))
    state = repo.get_state()
    assert state.active is False
    assert state.activated_by == "admin.two"
