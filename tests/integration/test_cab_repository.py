from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.adapters.persistence.cab_repository_sqlalchemy import SqlAlchemyCabRepository
from src.adapters.persistence.change_repository_sqlalchemy import SqlAlchemyChangeRepository
from src.domain.entities.cab_ticket import CabTicket
from src.domain.enums.actor_role import ActorRole
from tests.fixtures.builders import make_change_request


def _ticket(change_id: str, submitted_by: str = "dev.one") -> CabTicket:
    return CabTicket(
        ticket_id=f"tkt-{change_id}",
        change_id=change_id,
        executive_summary="summary",
        business_impact="impact",
        technical_impact="impact",
        risk_level="HIGH",
        triggered_controls=("RISK-001",),
        evidence=("a.py",),
        rollback_ready=True,
        maintenance_window_ready=True,
        dependencies=(),
        required_approver_roles=(ActorRole.APPROVER,),
        submitted_by=submitted_by,
        created_at=datetime.now(UTC),
    )


def test_create_and_get_ticket(db_session):
    change_repo = SqlAlchemyChangeRepository(db_session)
    change_repo.create(make_change_request(change_id="chg-cab-1"))
    repo = SqlAlchemyCabRepository(db_session)
    ticket = repo.create_ticket(_ticket("chg-cab-1"))

    fetched = repo.get_ticket(ticket.ticket_id)
    assert fetched.change_id == "chg-cab-1"
    assert repo.get_ticket_for_change("chg-cab-1").ticket_id == ticket.ticket_id


def test_record_decision_updates_ticket(db_session):
    change_repo = SqlAlchemyChangeRepository(db_session)
    change_repo.create(make_change_request(change_id="chg-cab-2"))
    repo = SqlAlchemyCabRepository(db_session)
    ticket = repo.create_ticket(_ticket("chg-cab-2"))

    decided = repo.record_decision(
        ticket.ticket_id,
        decision="APPROVED",
        rationale="looks fine",
        decided_by="approver.one",
        decided_role="approver",
    )
    assert decided.decision == "APPROVED"
    assert decided.decided_by == "approver.one"
    assert decided.decided_at is not None


def test_list_queue_only_returns_undecided(db_session):
    change_repo = SqlAlchemyChangeRepository(db_session)
    repo = SqlAlchemyCabRepository(db_session)
    for i in range(3):
        change_repo.create(make_change_request(change_id=f"chg-cab-q-{i}"))
        repo.create_ticket(_ticket(f"chg-cab-q-{i}"))

    repo.record_decision(
        "tkt-chg-cab-q-0", decision="REJECTED", rationale="no", decided_by="x", decided_role="approver"
    )

    queue, total = repo.list_queue()
    assert total == 2
    assert all(t.decision is None for t in queue)


def test_get_missing_ticket_raises(db_session):
    from src.ports.cab_repository import CabTicketNotFoundError

    repo = SqlAlchemyCabRepository(db_session)
    with pytest.raises(CabTicketNotFoundError):
        repo.get_ticket("does-not-exist")
