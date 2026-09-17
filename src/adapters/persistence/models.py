"""SQLAlchemy 2.x ORM models. PostgreSQL only — JSONB columns are used
throughout and this schema is not intended to be SQLite-compatible.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _uuid_str() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class ChangeORM(Base):
    __tablename__ = "changes"

    change_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    repository: Mapped[str] = mapped_column(String(512))
    branch: Mapped[str] = mapped_column(String(256))
    commit_sha: Mapped[str] = mapped_column(String(64))
    author: Mapped[str] = mapped_column(String(256))
    change_type: Mapped[str] = mapped_column(String(64))
    changed_files: Mapped[list] = mapped_column(JSONB, default=list)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    terraform_plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    migration_statements: Mapped[list] = mapped_column(JSONB, default=list)
    linked_work_item: Mapped[str | None] = mapped_column(String(256), nullable=True)
    maintenance_window_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    maintenance_window_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    has_rollback_plan: Mapped[bool] = mapped_column(Boolean, default=False)
    rollback_plan_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_dependencies: Mapped[list] = mapped_column(JSONB, default=list)
    environment_target: Mapped[str] = mapped_column(String(32))
    tests_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    change_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    state: Mapped[str] = mapped_column(String(32), default="PROPOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    risk_assessments: Mapped[list[RiskAssessmentORM]] = relationship(
        back_populates="change", cascade="all, delete-orphan", order_by="RiskAssessmentORM.created_at"
    )
    ai_assessments: Mapped[list[AIAssessmentORM]] = relationship(
        back_populates="change", cascade="all, delete-orphan", order_by="AIAssessmentORM.created_at"
    )
    gate_results: Mapped[list[GateResultORM]] = relationship(
        back_populates="change", cascade="all, delete-orphan", order_by="GateResultORM.created_at"
    )
    routing_decisions: Mapped[list[RoutingDecisionORM]] = relationship(
        back_populates="change", cascade="all, delete-orphan", order_by="RoutingDecisionORM.created_at"
    )
    cab_ticket: Mapped[CabTicketORM | None] = relationship(
        back_populates="change", cascade="all, delete-orphan", uselist=False
    )


class RiskAssessmentORM(Base):
    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.change_id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(16))
    triggered_rules: Mapped[list] = mapped_column(JSONB, default=list)
    blast_radius: Mapped[int] = mapped_column(Integer, default=0)
    blast_radius_description: Mapped[str] = mapped_column(Text, default="")
    required_governance_actions: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    change: Mapped[ChangeORM] = relationship(back_populates="risk_assessments")


class AIAssessmentORM(Base):
    __tablename__ = "ai_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.change_id", ondelete="CASCADE"))
    is_secondary: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_name: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str] = mapped_column(Text)
    impact_map: Mapped[list] = mapped_column(JSONB, default=list)
    dependency_concerns: Mapped[list] = mapped_column(JSONB, default=list)
    rollback_considerations: Mapped[list] = mapped_column(JSONB, default=list)
    cab_executive_brief: Mapped[str] = mapped_column(Text, default="")
    recommended_reviewer_roles: Mapped[list] = mapped_column(JSONB, default=list)
    referenced_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    recommended_route: Mapped[str] = mapped_column(String(32))
    suggested_risk_level: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    raw_response: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    change: Mapped[ChangeORM] = relationship(back_populates="ai_assessments")


class GateResultORM(Base):
    __tablename__ = "gate_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.change_id", ondelete="CASCADE"))
    gate: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    change: Mapped[ChangeORM] = relationship(back_populates="gate_results")


class RoutingDecisionORM(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[str] = mapped_column(ForeignKey("changes.change_id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(String(32))
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    policy_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    change: Mapped[ChangeORM] = relationship(back_populates="routing_decisions")


class CabTicketORM(Base):
    __tablename__ = "cab_tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid_str)
    change_id: Mapped[str] = mapped_column(
        ForeignKey("changes.change_id", ondelete="CASCADE"), unique=True
    )
    executive_summary: Mapped[str] = mapped_column(Text)
    business_impact: Mapped[str] = mapped_column(Text)
    technical_impact: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(16))
    triggered_controls: Mapped[list] = mapped_column(JSONB, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    rollback_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    maintenance_window_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    dependencies: Mapped[list] = mapped_column(JSONB, default=list)
    required_approver_roles: Mapped[list] = mapped_column(JSONB, default=list)
    submitted_by: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    decided_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    change: Mapped[ChangeORM] = relationship(back_populates="cab_ticket")


class AuditRecordORM(Base):
    __tablename__ = "audit_records"
    __table_args__ = (UniqueConstraint("sequence", name="uq_audit_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    actor: Mapped[str] = mapped_column(String(256))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(128))
    entity_id: Mapped[str] = mapped_column(String(128))
    previous_hash: Mapped[str] = mapped_column(String(64))
    canonical_payload: Mapped[str] = mapped_column(Text)
    current_hash: Mapped[str] = mapped_column(String(64))


class KillSwitchStateORM(Base):
    __tablename__ = "kill_switch_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_by: Mapped[str | None] = mapped_column(String(256), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
