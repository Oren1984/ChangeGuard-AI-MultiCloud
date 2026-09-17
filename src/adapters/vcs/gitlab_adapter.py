from __future__ import annotations

from src.adapters.vcs.common import parse_changeguard_extension, require
from src.domain.entities.change_request import ChangeRequest


class GitLabVCSProvider:
    """Normalizes a (simulated) GitLab merge_request webhook payload, enriched
    with a `changeguard` governance extension block, into a ChangeRequest."""

    provider_name = "gitlab"

    def normalize(self, raw_payload: dict) -> ChangeRequest:
        project_path = require(raw_payload, "project", "path_with_namespace")
        mr = require(raw_payload, "merge_request")
        branch = require(mr, "source_branch")
        commit_sha = require(mr, "last_commit", "id")
        author = require(mr, "author", "username")

        ext = parse_changeguard_extension(raw_payload)

        return ChangeRequest(
            change_id=ext["change_id"],
            repository=project_path,
            branch=branch,
            commit_sha=commit_sha,
            author=author,
            change_type=ext["change_type"],
            changed_files=tuple(raw_payload.get("files", [])),
            diff=raw_payload.get("diff"),
            terraform_plan=ext["terraform_plan"],
            migration_statements=ext["migration_statements"],
            linked_work_item=ext["linked_work_item"],
            planned_maintenance_window=ext["planned_maintenance_window"],
            has_rollback_plan=ext["has_rollback_plan"],
            rollback_plan_description=ext["rollback_plan_description"],
            service_dependencies=ext["service_dependencies"],
            environment_target=ext["environment_target"],
            tests_passed=ext["tests_passed"],
            submitted_by=author,
            metadata=ext["metadata"],
        )
