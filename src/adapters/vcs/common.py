"""Shared parsing helpers for VCS adapters.

Real GitHub/GitLab webhooks don't natively carry governance fields such as
change type, Terraform plan evidence, or rollback status — those come from
the CI pipeline that fronts the webhook call. Both adapters therefore expect
an additional `changeguard` extension block alongside the native
provider payload. This mirrors how a real integration would work: a CI job
enriches the native webhook with governance metadata before forwarding it to
ChangeGuard's intake endpoint.
"""

from __future__ import annotations

from datetime import datetime

from src.domain.entities.change_request import (
    MaintenanceWindow,
    TerraformPlanEvidence,
    TerraformResourceChange,
)
from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment
from src.ports.vcs_provider import VCSNormalizationError


def require(payload: dict, *path: str):
    node = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise VCSNormalizationError(f"missing required field: {'.'.join(path)}")
        node = node[key]
    return node


def parse_changeguard_extension(payload: dict) -> dict:
    ext = payload.get("changeguard")
    if not isinstance(ext, dict):
        raise VCSNormalizationError("missing required 'changeguard' governance extension block")
    if "change_id" not in ext or "change_type" not in ext:
        raise VCSNormalizationError("'changeguard' block must include change_id and change_type")

    try:
        change_type = ChangeType(ext["change_type"])
    except ValueError as exc:
        raise VCSNormalizationError(f"unknown change_type: {ext['change_type']}") from exc

    try:
        environment_target = Environment(ext.get("environment_target", "dev"))
    except ValueError as exc:
        raise VCSNormalizationError(f"unknown environment_target: {ext.get('environment_target')}") from exc

    terraform_plan = None
    if ext.get("terraform_plan"):
        raw_plan = ext["terraform_plan"]
        terraform_plan = TerraformPlanEvidence(
            resource_changes=tuple(
                TerraformResourceChange(
                    address=rc["address"],
                    resource_type=rc["resource_type"],
                    actions=tuple(rc["actions"]),
                    attributes=rc.get("attributes", {}),
                )
                for rc in raw_plan.get("resource_changes", [])
            ),
            raw_plan_json=raw_plan,
        )

    window = None
    raw_window = ext.get("planned_maintenance_window")
    if raw_window:
        window = MaintenanceWindow(
            starts_at=(
                datetime.fromisoformat(raw_window["starts_at"]) if raw_window.get("starts_at") else None
            ),
            ends_at=datetime.fromisoformat(raw_window["ends_at"]) if raw_window.get("ends_at") else None,
        )

    return {
        "change_id": ext["change_id"],
        "change_type": change_type,
        "terraform_plan": terraform_plan,
        "migration_statements": tuple(ext.get("migration_statements", [])),
        "linked_work_item": ext.get("linked_work_item"),
        "planned_maintenance_window": window,
        "has_rollback_plan": bool(ext.get("has_rollback_plan", False)),
        "rollback_plan_description": ext.get("rollback_plan_description"),
        "service_dependencies": tuple(ext.get("service_dependencies", [])),
        "environment_target": environment_target,
        "tests_passed": ext.get("tests_passed"),
        "metadata": ext.get("metadata", {}),
    }
