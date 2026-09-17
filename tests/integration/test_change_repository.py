from __future__ import annotations

import pytest

from src.adapters.persistence.change_repository_sqlalchemy import SqlAlchemyChangeRepository
from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.risk_assessment import RiskAssessment, TriggeredRule
from src.domain.enums.change_state import ChangeState
from src.domain.enums.risk_level import RiskLevel
from tests.fixtures.builders import make_change_request


def test_create_and_get_round_trips_all_fields(db_session):
    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-001", changed_files=("a.py", "b.py"))
    record = repo.create(change)

    assert record.change.change_id == "chg-int-001"
    assert record.state == ChangeState.PROPOSED

    fetched = repo.get("chg-int-001")
    assert fetched.change.changed_files == ("a.py", "b.py")
    assert fetched.change.repository == change.repository


def test_duplicate_change_id_raises(db_session):
    from src.ports.change_repository import DuplicateChangeError

    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-dup")
    repo.create(change)
    with pytest.raises(DuplicateChangeError):
        repo.create(change)


def test_get_missing_change_raises(db_session):
    from src.ports.change_repository import ChangeNotFoundError

    repo = SqlAlchemyChangeRepository(db_session)
    with pytest.raises(ChangeNotFoundError):
        repo.get("does-not-exist")


def test_update_state_persists(db_session):
    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-state")
    repo.create(change)
    record = repo.update_state("chg-int-state", ChangeState.RISK_EVALUATED)
    assert record.state == ChangeState.RISK_EVALUATED
    assert repo.get("chg-int-state").state == ChangeState.RISK_EVALUATED


def test_attach_risk_assessment_jsonb_round_trip(db_session):
    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-risk")
    repo.create(change)

    risk = RiskAssessment(
        score=42,
        level=RiskLevel.MEDIUM,
        triggered_rules=(
            TriggeredRule(
                rule_id="RISK-TEST-001",
                category="test",
                severity=42,
                description="test rule",
                evidence=("a.py",),
                required_action="do something",
            ),
        ),
        blast_radius=2,
        blast_radius_description="limited",
        required_governance_actions=("do something",),
    )
    record = repo.attach_risk_assessment("chg-int-risk", risk)
    assert record.risk_assessment is not None
    assert record.risk_assessment.score == 42
    assert record.risk_assessment.triggered_rules[0].rule_id == "RISK-TEST-001"
    assert record.risk_assessment.triggered_rules[0].evidence == ("a.py",)


def test_attach_primary_and_secondary_ai_assessment(db_session):
    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-ai")
    repo.create(change)

    def build(name: str) -> AIAssessment:
        return AIAssessment(
            provider_name=name,
            summary="summary",
            impact_map=(),
            dependency_concerns=(),
            rollback_considerations=(),
            cab_executive_brief="brief",
            recommended_reviewer_roles=("operator",),
            referenced_evidence=(),
            recommended_route="AUTO_CLEAR",
            suggested_risk_level=RiskLevel.LOW,
            confidence=0.9,
        )

    repo.attach_ai_assessment("chg-int-ai", build("primary"), secondary=False)
    record = repo.attach_ai_assessment("chg-int-ai", build("secondary"), secondary=True)

    assert record.ai_assessment.provider_name == "primary"
    assert record.secondary_ai_assessment.provider_name == "secondary"


def test_list_filters_by_state_and_paginates(db_session):
    repo = SqlAlchemyChangeRepository(db_session)
    for i in range(5):
        repo.create(make_change_request(change_id=f"chg-int-list-{i}"))
    repo.update_state("chg-int-list-0", ChangeState.RISK_EVALUATED)

    all_records, total = repo.list(limit=2, offset=0)
    assert total == 5
    assert len(all_records) == 2

    risk_evaluated, risk_total = repo.list(state=ChangeState.RISK_EVALUATED)
    assert risk_total == 1
    assert risk_evaluated[0].change.change_id == "chg-int-list-0"


def test_cascade_delete_removes_children(db_session):
    from src.adapters.persistence.models import ChangeORM

    repo = SqlAlchemyChangeRepository(db_session)
    change = make_change_request(change_id="chg-int-cascade")
    repo.create(change)
    risk = RiskAssessment(score=1, level=RiskLevel.LOW)
    repo.attach_risk_assessment("chg-int-cascade", risk)

    orm = db_session.get(ChangeORM, "chg-int-cascade")
    db_session.delete(orm)
    db_session.commit()

    from sqlalchemy import select

    from src.adapters.persistence.models import RiskAssessmentORM

    remaining = db_session.execute(
        select(RiskAssessmentORM).where(RiskAssessmentORM.change_id == "chg-int-cascade")
    ).scalars().all()
    assert remaining == []
