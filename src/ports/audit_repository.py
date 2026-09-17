from __future__ import annotations

from typing import Protocol

from src.domain.entities.audit_record import AuditRecord
from src.domain.policies.audit_chain import ChainVerificationResult


class AuditPersistenceError(Exception):
    """Raised when an audit record cannot be durably persisted. Any action
    that cannot be audited must not be considered to have happened."""


class AuditRepository(Protocol):
    def append(
        self,
        *,
        actor: str,
        actor_role: str,
        action: str,
        entity_id: str,
        payload: dict,
    ) -> AuditRecord:
        """Appends a new hash-chained record. Raises AuditPersistenceError on failure."""
        ...

    def verify_chain(self) -> ChainVerificationResult:
        ...

    def list_recent(self, limit: int = 50) -> list[AuditRecord]:
        ...

    def list_for_entity(self, entity_id: str) -> list[AuditRecord]:
        ...
