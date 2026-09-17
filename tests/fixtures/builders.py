"""Shared test-data factories used across unit, integration, assurance,
security, and e2e test layers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.domain.entities.change_request import ChangeRequest
from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment


def make_change_request(**overrides) -> ChangeRequest:
    defaults = dict(
        change_id=overrides.pop("change_id", f"chg-{uuid.uuid4().hex[:10]}"),
        repository="org/service-a",
        branch="feature/change",
        commit_sha="a" * 40,
        author="dev.one",
        change_type=ChangeType.APPLICATION_CODE,
        changed_files=("src/app/handlers.py",),
        diff="- old\n+ new",
        has_rollback_plan=True,
        environment_target=Environment.STAGING,
        tests_passed=True,
        submitted_by="dev.one",
        submitted_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return ChangeRequest(**defaults)
