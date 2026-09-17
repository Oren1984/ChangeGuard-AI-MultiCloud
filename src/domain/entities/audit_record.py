from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """One entry in the hash-chained, tamper-evident audit trail.

    `current_hash` = SHA-256(previous_hash || canonical_payload). See
    src/domain/policies/audit_chain.py for the canonicalization and hashing
    rules — they must be applied identically at write and verify time.
    """

    sequence: int
    timestamp: datetime
    actor: str
    actor_role: str
    action: str
    entity_id: str
    previous_hash: str
    canonical_payload: str
    current_hash: str
