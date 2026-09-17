from __future__ import annotations

from sqlalchemy import text

from src.adapters.persistence.audit_repository_sqlalchemy import SqlAlchemyAuditRepository


def test_append_builds_a_valid_chain(db_session):
    repo = SqlAlchemyAuditRepository(db_session)
    for i in range(5):
        repo.append(
            actor="tester",
            actor_role="admin",
            action="TEST_EVENT",
            entity_id=f"entity-{i}",
            payload={"i": i},
        )

    result = repo.verify_chain()
    assert result.is_valid
    assert result.total_records == 5


def test_sequence_is_strictly_increasing_and_chained(db_session):
    repo = SqlAlchemyAuditRepository(db_session)
    first = repo.append(actor="a", actor_role="admin", action="E1", entity_id="x", payload={})
    second = repo.append(actor="a", actor_role="admin", action="E2", entity_id="x", payload={})
    assert second.sequence == first.sequence + 1
    assert second.previous_hash == first.current_hash


def test_tampering_with_a_historical_record_is_detected(db_session):
    repo = SqlAlchemyAuditRepository(db_session)
    repo.append(actor="a", actor_role="admin", action="E1", entity_id="x", payload={"amount": 100})
    repo.append(actor="a", actor_role="admin", action="E2", entity_id="x", payload={"amount": 200})

    # Simulate an attacker directly mutating a historical row in the DB.
    db_session.execute(
        text("UPDATE audit_records SET canonical_payload = :p WHERE sequence = 1"),
        {"p": '{"tampered":true}'},
    )
    db_session.commit()

    result = repo.verify_chain()
    assert not result.is_valid
    assert result.first_invalid_sequence == 1
    assert "tampered" in result.reason.lower() or "hash" in result.reason.lower()


def test_deleting_a_record_creates_a_sequence_discontinuity(db_session):
    repo = SqlAlchemyAuditRepository(db_session)
    repo.append(actor="a", actor_role="admin", action="E1", entity_id="x", payload={})
    repo.append(actor="a", actor_role="admin", action="E2", entity_id="x", payload={})
    repo.append(actor="a", actor_role="admin", action="E3", entity_id="x", payload={})

    db_session.execute(text("DELETE FROM audit_records WHERE sequence = 2"))
    db_session.commit()

    result = repo.verify_chain()
    assert not result.is_valid
    assert result.first_invalid_sequence == 3


def test_list_for_entity_returns_only_matching_records(db_session):
    repo = SqlAlchemyAuditRepository(db_session)
    repo.append(actor="a", actor_role="admin", action="E1", entity_id="chg-1", payload={})
    repo.append(actor="a", actor_role="admin", action="E2", entity_id="chg-2", payload={})
    repo.append(actor="a", actor_role="admin", action="E3", entity_id="chg-1", payload={})

    records = repo.list_for_entity("chg-1")
    assert len(records) == 2
    assert all(r.entity_id == "chg-1" for r in records)
