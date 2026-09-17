from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import ChangeRequest
from src.ports.audit_repository import AuditRepository
from src.ports.change_repository import ChangeRepository, DuplicateChangeError


@dataclass(frozen=True, slots=True)
class SubmitChangeResult:
    record: ChangeRecord
    created: bool  # False when this was an idempotent replay of an existing change_id


class SubmitChangeUseCase:
    """Intake for a normalized change. Idempotent on change_id: a repeated
    webhook delivery for the same change_id returns the existing record
    instead of erroring or creating a duplicate."""

    def __init__(self, change_repo: ChangeRepository, audit_repo: AuditRepository) -> None:
        self._change_repo = change_repo
        self._audit_repo = audit_repo

    def execute(self, change: ChangeRequest, *, actor: str, actor_role: str) -> SubmitChangeResult:
        if self._change_repo.exists(change.change_id):
            return SubmitChangeResult(record=self._change_repo.get(change.change_id), created=False)

        try:
            record = self._change_repo.create(change)
        except DuplicateChangeError:
            return SubmitChangeResult(record=self._change_repo.get(change.change_id), created=False)

        self._audit_repo.append(
            actor=actor,
            actor_role=actor_role,
            action="CHANGE_SUBMITTED",
            entity_id=change.change_id,
            payload={
                "repository": change.repository,
                "change_type": change.change_type.value,
                "environment_target": change.environment_target.value,
            },
        )
        return SubmitChangeResult(record=record, created=True)
