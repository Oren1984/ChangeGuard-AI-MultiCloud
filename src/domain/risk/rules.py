"""Deterministic risk rule catalog.

Each rule is a small pure function: ChangeRequest -> TriggeredRule | None.
Rules are intentionally plain Python functions rather than a bespoke rule
DSL — this stays easy to read, easy to unit test in isolation, and easy to
extend without building a rule-language interpreter nobody asked for.

Severity scale: 0-100.
  * severity >= 90  => "mandatory" rule; RiskAssessment.has_mandatory_violation
                       becomes True and the routing policy treats it as an
                       automatic hard-block candidate regardless of AI input.
  * severity 50-89   => contributes heavily toward HIGH/CRITICAL.
  * severity < 50     => contributes toward LOW/MEDIUM.
"""

from __future__ import annotations

from collections.abc import Callable

from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.risk_assessment import TriggeredRule
from src.domain.enums.change_type import ChangeType

RuleFn = Callable[[ChangeRequest], "TriggeredRule | None"]

_PUBLIC_CIDRS = {"0.0.0.0/0", "::/0"}
_SENSITIVE_KEYWORDS = ("secret", "password", "passwd", "token", "api_key", "apikey", "private_key")
_SECURITY_RESOURCE_TYPES = (
    "aws_security_group",
    "aws_iam_policy",
    "aws_iam_role_policy",
    "aws_wafv2_web_acl",
    "google_compute_firewall",
    "google_project_iam_policy",
)
_DROP_PATTERN = ("drop table", "drop database", "drop column", "drop index", "truncate table")
_IRREVERSIBLE_ALTER = ("alter table", "drop column")


def rule_public_network_exposure(change: ChangeRequest) -> TriggeredRule | None:
    if not change.terraform_plan:
        return None
    hits: list[str] = []
    for rc in change.terraform_plan.resource_changes:
        cidrs = _extract_cidrs(rc.attributes)
        if cidrs & _PUBLIC_CIDRS:
            hits.append(f"{rc.address} exposes {sorted(cidrs & _PUBLIC_CIDRS)}")
    if not hits:
        return None
    severity = 95 if change.is_production_target else 75
    return TriggeredRule(
        rule_id="RISK-NET-001",
        category="network_exposure",
        severity=severity,
        description="Terraform plan opens public network access (0.0.0.0/0 or ::/0).",
        evidence=tuple(hits),
        required_action="Restrict CIDR ranges to approved network segments before deployment.",
    )


def rule_destructive_terraform_operations(change: ChangeRequest) -> TriggeredRule | None:
    if not change.terraform_plan:
        return None
    deletes = [
        rc.address
        for rc in change.terraform_plan.resource_changes
        if "delete" in rc.actions and "create" not in rc.actions
    ]
    if not deletes:
        return None
    severity = 90 if change.is_production_target else 65
    return TriggeredRule(
        rule_id="RISK-TF-001",
        category="destructive_infrastructure",
        severity=severity,
        description="Terraform plan permanently deletes one or more resources.",
        evidence=tuple(deletes),
        required_action="Confirm deletion is intentional and a rollback/backup exists.",
    )


def rule_resource_replacement(change: ChangeRequest) -> TriggeredRule | None:
    if not change.terraform_plan:
        return None
    replaces = [
        rc.address
        for rc in change.terraform_plan.resource_changes
        if "delete" in rc.actions and "create" in rc.actions
    ]
    if not replaces:
        return None
    return TriggeredRule(
        rule_id="RISK-TF-002",
        category="resource_replacement",
        severity=55,
        description="Terraform plan replaces (delete + recreate) one or more resources.",
        evidence=tuple(replaces),
        required_action="Verify replacement does not cause unacceptable downtime or data loss.",
    )


def rule_iam_wildcard_privileges(change: ChangeRequest) -> TriggeredRule | None:
    if change.change_type != ChangeType.IAM_POLICY:
        return None
    haystacks = [change.diff or ""]
    if change.terraform_plan:
        for rc in change.terraform_plan.resource_changes:
            haystacks.append(str(rc.attributes))
    text = "\n".join(haystacks)
    if '"Action": "*"' not in text and "'*'" not in text and '"*"' not in text:
        return None
    return TriggeredRule(
        rule_id="RISK-IAM-001",
        category="iam_wildcard",
        severity=95,
        description="IAM policy change grants wildcard (*) action or resource privileges.",
        evidence=("wildcard '*' found in IAM policy statement",),
        required_action="Scope IAM permissions to least-privilege actions and resources.",
    )


def rule_security_control_removal(change: ChangeRequest) -> TriggeredRule | None:
    if not change.terraform_plan:
        return None
    removed = [
        rc.address
        for rc in change.terraform_plan.resource_changes
        if rc.resource_type in _SECURITY_RESOURCE_TYPES and "delete" in rc.actions
    ]
    if not removed:
        return None
    return TriggeredRule(
        rule_id="RISK-SEC-001",
        category="security_control_removal",
        severity=85,
        description="A security control (firewall/security-group/IAM policy) is being removed.",
        evidence=tuple(removed),
        required_action="Require security-reviewer sign-off before proceeding.",
    )


def rule_destructive_db_migration(change: ChangeRequest) -> TriggeredRule | None:
    if not change.migration_statements:
        return None
    hits = [
        stmt
        for stmt in change.migration_statements
        if any(p in stmt.lower() for p in _DROP_PATTERN)
    ]
    if not hits:
        return None
    severity = 90 if change.is_production_target else 70
    return TriggeredRule(
        rule_id="RISK-DB-001",
        category="destructive_migration",
        severity=severity,
        description="Database migration contains a destructive statement (DROP/TRUNCATE).",
        evidence=tuple(hits),
        required_action="Confirm a verified backup and rollback script exist before applying.",
    )


def rule_irreversible_alter(change: ChangeRequest) -> TriggeredRule | None:
    if not change.migration_statements:
        return None
    hits = [
        stmt
        for stmt in change.migration_statements
        if "alter table" in stmt.lower() and "drop column" in stmt.lower()
    ]
    if not hits:
        return None
    return TriggeredRule(
        rule_id="RISK-DB-002",
        category="irreversible_migration",
        severity=75,
        description="Migration drops a column via ALTER TABLE; this is not reversible without a backup.",
        evidence=tuple(hits),
        required_action="Provide a data-preserving rollback plan or a verified backup.",
    )


def rule_production_schema_change_without_rollback(change: ChangeRequest) -> TriggeredRule | None:
    if change.change_type != ChangeType.DB_MIGRATION or not change.is_production_target:
        return None
    if change.has_rollback_plan:
        return None
    return TriggeredRule(
        rule_id="RISK-DB-003",
        category="rollback_missing",
        severity=60,
        description="Production schema change submitted without rollback evidence.",
        evidence=("has_rollback_plan=false",),
        required_action="Attach a rollback script or restore procedure before CAB review.",
    )


def rule_missing_rollback_plan(change: ChangeRequest) -> TriggeredRule | None:
    high_impact_types = {ChangeType.DB_MIGRATION, ChangeType.TERRAFORM_PLAN, ChangeType.IAM_POLICY}
    if change.change_type not in high_impact_types or not change.is_production_target:
        return None
    if change.has_rollback_plan:
        return None
    return TriggeredRule(
        rule_id="RISK-OPS-001",
        category="rollback_missing",
        severity=50,
        description="High-impact production change has no documented rollback plan.",
        evidence=("has_rollback_plan=false",),
        required_action="Document a rollback procedure.",
    )


def rule_missing_maintenance_window(change: ChangeRequest) -> TriggeredRule | None:
    high_impact_types = {ChangeType.DB_MIGRATION, ChangeType.TERRAFORM_PLAN, ChangeType.IAM_POLICY}
    if change.change_type not in high_impact_types or not change.is_production_target:
        return None
    window = change.planned_maintenance_window
    if window is not None and window.is_defined:
        return None
    return TriggeredRule(
        rule_id="RISK-OPS-002",
        category="maintenance_window_missing",
        severity=40,
        description="High-impact production change has no planned maintenance window.",
        evidence=("planned_maintenance_window=undefined",),
        required_action="Schedule a maintenance window before deployment.",
    )


def rule_api_breaking_change(change: ChangeRequest) -> TriggeredRule | None:
    if change.change_type != ChangeType.API_CONTRACT:
        return None
    is_breaking = bool(change.metadata.get("breaking_change"))
    diff_flagged = bool(change.diff) and "BREAKING CHANGE" in (change.diff or "")
    if not (is_breaking or diff_flagged):
        return None
    return TriggeredRule(
        rule_id="RISK-API-001",
        category="api_breaking_change",
        severity=55,
        description="API contract change is marked as breaking for downstream consumers.",
        evidence=("metadata.breaking_change=true" if is_breaking else "diff contains 'BREAKING CHANGE'",),
        required_action="Coordinate a deprecation window with all dependent service owners.",
    )


def rule_high_blast_radius(change: ChangeRequest) -> TriggeredRule | None:
    if change.dependency_count < 3:
        return None
    severity = min(30 + change.dependency_count * 5, 70)
    return TriggeredRule(
        rule_id="RISK-BLAST-001",
        category="blast_radius",
        severity=severity,
        description=f"Change affects {change.dependency_count} dependent services.",
        evidence=change.service_dependencies,
        required_action="Notify all dependent service owners prior to deployment.",
    )


def rule_missing_or_failed_tests(change: ChangeRequest) -> TriggeredRule | None:
    if change.tests_passed is False:
        return TriggeredRule(
            rule_id="RISK-QA-001",
            category="test_failure",
            severity=50,
            description="Automated tests for this change are failing.",
            evidence=("tests_passed=false",),
            required_action="Do not proceed until the test suite passes.",
        )
    if change.tests_passed is None:
        return TriggeredRule(
            rule_id="RISK-QA-002",
            category="test_missing",
            severity=30,
            description="No test result evidence was submitted with this change.",
            evidence=("tests_passed=unknown",),
            required_action="Attach CI test results before evaluation.",
        )
    return None


def rule_large_change_size(change: ChangeRequest) -> TriggeredRule | None:
    if change.changed_file_count <= 40:
        return None
    return TriggeredRule(
        rule_id="RISK-SIZE-001",
        category="change_size",
        severity=25,
        description=f"Change touches an unusually large number of files ({change.changed_file_count}).",
        evidence=(f"changed_file_count={change.changed_file_count}",),
        required_action="Consider splitting into smaller, independently reviewable changes.",
    )


def rule_production_target(change: ChangeRequest) -> TriggeredRule | None:
    if not change.is_production_target:
        return None
    return TriggeredRule(
        rule_id="RISK-ENV-001",
        category="production_target",
        severity=10,
        description="Change targets the production environment.",
        evidence=("environment_target=production",),
        required_action="Apply standard production change controls.",
    )


def rule_sensitive_configuration_change(change: ChangeRequest) -> TriggeredRule | None:
    if change.change_type != ChangeType.CONFIGURATION:
        return None
    haystack = " ".join(change.changed_files).lower() + " " + (change.diff or "").lower()
    hits = [kw for kw in _SENSITIVE_KEYWORDS if kw in haystack]
    if not hits:
        return None
    return TriggeredRule(
        rule_id="RISK-CFG-001",
        category="sensitive_configuration",
        severity=45,
        description="Configuration change touches sensitive-looking keys (secrets/tokens/credentials).",
        evidence=tuple(hits),
        required_action="Confirm secrets are sourced from a secret manager, not committed in plaintext.",
    )


def _extract_cidrs(attributes: dict) -> set[str]:
    found: set[str] = set()
    for value in attributes.values():
        if isinstance(value, str) and "/" in value:
            found.add(value)
        elif isinstance(value, list | tuple):
            for item in value:
                if isinstance(item, str) and "/" in item:
                    found.add(item)
                elif isinstance(item, dict):
                    found |= _extract_cidrs(item)
        elif isinstance(value, dict):
            found |= _extract_cidrs(value)
    return found


RULE_REGISTRY: tuple[RuleFn, ...] = (
    rule_public_network_exposure,
    rule_destructive_terraform_operations,
    rule_resource_replacement,
    rule_iam_wildcard_privileges,
    rule_security_control_removal,
    rule_destructive_db_migration,
    rule_irreversible_alter,
    rule_production_schema_change_without_rollback,
    rule_missing_rollback_plan,
    rule_missing_maintenance_window,
    rule_api_breaking_change,
    rule_high_blast_radius,
    rule_missing_or_failed_tests,
    rule_large_change_size,
    rule_production_target,
    rule_sensitive_configuration_change,
)
