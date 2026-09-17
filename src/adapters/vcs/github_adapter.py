from __future__ import annotations

from src.adapters.vcs.common import parse_changeguard_extension, require
from src.domain.entities.change_request import ChangeRequest
from src.ports.vcs_provider import VCSNormalizationError


class GitHubVCSProvider:
    """Normalizes a (simulated) GitHub pull_request webhook payload, enriched
    with a `changeguard` governance extension block, into a ChangeRequest."""

    provider_name = "github"

    def normalize(self, raw_payload: dict) -> ChangeRequest:
        try:
            repo_full_name = require(raw_payload, "repository", "full_name")
            pr = require(raw_payload, "pull_request")
            branch = require(pr, "head", "ref")
            commit_sha = require(pr, "head", "sha")
            author = require(pr, "user", "login")
        except VCSNormalizationError:
            raise

        ext = parse_changeguard_extension(raw_payload)

        return ChangeRequest(
            change_id=ext["change_id"],
            repository=repo_full_name,
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
