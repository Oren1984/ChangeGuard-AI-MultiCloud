from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment


@dataclass(frozen=True, slots=True)
class TerraformResourceChange:
    """A single resource change extracted from a Terraform plan."""

    address: str
    resource_type: str
    actions: tuple[str, ...]  # e.g. ("create",), ("delete",), ("delete", "create")
    attributes: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TerraformPlanEvidence:
    resource_changes: tuple[TerraformResourceChange, ...] = ()
    raw_plan_json: dict | None = None


@dataclass(frozen=True, slots=True)
class MaintenanceWindow:
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @property
    def is_defined(self) -> bool:
        return self.starts_at is not None and self.ends_at is not None


@dataclass(frozen=True, slots=True)
class ChangeRequest:
    """Normalized, provider-independent representation of a proposed change.

    This is the single evidence object the deterministic risk engine and the
    AI provider both operate on. It must never depend on FastAPI, SQLAlchemy,
    or any specific VCS/cloud SDK.
    """

    change_id: str
    repository: str
    branch: str
    commit_sha: str
    author: str
    change_type: ChangeType
    changed_files: tuple[str, ...] = ()
    diff: str | None = None
    terraform_plan: TerraformPlanEvidence | None = None
    migration_statements: tuple[str, ...] = ()
    linked_work_item: str | None = None
    planned_maintenance_window: MaintenanceWindow | None = None
    has_rollback_plan: bool = False
    rollback_plan_description: str | None = None
    service_dependencies: tuple[str, ...] = ()
    environment_target: Environment = Environment.DEV
    tests_passed: bool | None = None  # None = unknown/missing
    submitted_by: str | None = None
    submitted_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = field(default_factory=dict)

    @property
    def changed_file_count(self) -> int:
        return len(self.changed_files)

    @property
    def dependency_count(self) -> int:
        return len(self.service_dependencies)

    @property
    def is_production_target(self) -> bool:
        return self.environment_target == Environment.PRODUCTION
