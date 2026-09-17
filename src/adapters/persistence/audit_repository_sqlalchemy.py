from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.adapters.persistence.models import AuditRecordORM
from src.domain.entities.audit_record import AuditRecord
from src.domain.policies.audit_chain import (
    GENESIS_HASH,
    ChainLink,
    ChainVerificationResult,
    canonicalize_payload,
    compute_hash,
    verify_chain,
)
from src.ports.audit_repository import AuditPersistenceError


class SqlAlchemyAuditRepository:
    """Hash-chained, append-only audit trail.

    `append` locks the latest row (SELECT ... FOR UPDATE) before computing
    the next sequence/hash so concurrent writers cannot race and produce two
    records claiming the same previous_hash.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(
        self, *, actor: str, actor_role: str, action: str, entity_id: str, payload: dict
    ) -> AuditRecord:
        try:
            latest = self._session.execute(
                select(AuditRecordORM).order_by(AuditRecordORM.sequence.desc()).limit(1).with_for_update()
            ).scalar_one_or_none()

            previous_hash = latest.current_hash if latest else GENESIS_HASH
            next_sequence = (latest.sequence + 1) if latest else 1
            timestamp = datetime.now(UTC)

            canonical = canonicalize_payload(
                {
                    "sequence": next_sequence,
                    "timestamp": timestamp.isoformat(),
                    "actor": actor,
                    "actor_role": actor_role,
                    "action": action,
                    "entity_id": entity_id,
                    "payload": payload,
                }
            )
            current_hash = compute_hash(previous_hash, canonical)

            orm = AuditRecordORM(
                sequence=next_sequence,
                timestamp=timestamp,
                actor=actor,
                actor_role=actor_role,
                action=action,
                entity_id=entity_id,
                previous_hash=previous_hash,
                canonical_payload=canonical,
                current_hash=current_hash,
            )
            self._session.add(orm)
            self._session.commit()
        except Exception as exc:
            self._session.rollback()
            raise AuditPersistenceError(f"failed to append audit record: {exc}") from exc

        return AuditRecord(
            sequence=orm.sequence,
            timestamp=orm.timestamp,
            actor=orm.actor,
            actor_role=orm.actor_role,
            action=orm.action,
            entity_id=orm.entity_id,
            previous_hash=orm.previous_hash,
            canonical_payload=orm.canonical_payload,
            current_hash=orm.current_hash,
        )

    def verify_chain(self) -> ChainVerificationResult:
        rows = (
            self._session.execute(select(AuditRecordORM).order_by(AuditRecordORM.sequence.asc()))
            .scalars()
            .all()
        )
        links = [
            ChainLink(
                sequence=r.sequence,
                previous_hash=r.previous_hash,
                canonical_payload=r.canonical_payload,
                current_hash=r.current_hash,
            )
            for r in rows
        ]
        return verify_chain(links)

    def list_recent(self, limit: int = 50) -> list[AuditRecord]:
        rows = (
            self._session.execute(select(AuditRecordORM).order_by(AuditRecordORM.sequence.desc()).limit(limit))
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows]

    def list_for_entity(self, entity_id: str) -> list[AuditRecord]:
        rows = (
            self._session.execute(
                select(AuditRecordORM)
                .where(AuditRecordORM.entity_id == entity_id)
                .order_by(AuditRecordORM.sequence.asc())
            )
            .scalars()
            .all()
        )
        return [self._to_entity(r) for r in rows]

    @staticmethod
    def _to_entity(orm: AuditRecordORM) -> AuditRecord:
        return AuditRecord(
            sequence=orm.sequence,
            timestamp=orm.timestamp,
            actor=orm.actor,
            actor_role=orm.actor_role,
            action=orm.action,
            entity_id=orm.entity_id,
            previous_hash=orm.previous_hash,
            canonical_payload=orm.canonical_payload,
            current_hash=orm.current_hash,
        )
