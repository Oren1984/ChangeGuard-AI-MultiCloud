from __future__ import annotations

from sqlalchemy import inspect

from src.adapters.persistence.models import Base

EXPECTED_TABLES = {
    "changes",
    "risk_assessments",
    "ai_assessments",
    "gate_results",
    "routing_decisions",
    "cab_tickets",
    "audit_records",
    "kill_switch_state",
}


def test_all_orm_tables_exist_after_migration(engine):
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    assert EXPECTED_TABLES <= existing


def test_orm_metadata_matches_expected_table_set():
    assert {t.name for t in Base.metadata.tables.values()} == EXPECTED_TABLES


def test_changes_table_has_expected_primary_key(engine):
    inspector = inspect(engine)
    pk = inspector.get_pk_constraint("changes")
    assert pk["constrained_columns"] == ["change_id"]


def test_cascade_delete_rule_is_present(engine):
    inspector = inspect(engine)
    fks = inspector.get_foreign_keys("risk_assessments")
    assert any(fk["options"].get("ondelete") == "CASCADE" for fk in fks)
