from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.domain.entities.change_request import (
    ChangeRequest,
    MaintenanceWindow,
    TerraformPlanEvidence,
    TerraformResourceChange,
)
from src.domain.enums.change_type import ChangeType
from src.domain.enums.environment import Environment


@pytest.fixture
def low_risk_app_change() -> ChangeRequest:
    return ChangeRequest(
        change_id="chg-low-001",
        repository="org/service-a",
        branch="feature/small-fix",
        commit_sha="a" * 40,
        author="dev.one",
        change_type=ChangeType.APPLICATION_CODE,
        changed_files=("src/app/handlers.py", "tests/test_handlers.py"),
        diff="- old\n+ new",
        has_rollback_plan=True,
        service_dependencies=(),
        environment_target=Environment.STAGING,
        tests_passed=True,
    )


@pytest.fixture
def public_exposure_terraform_change() -> ChangeRequest:
    plan = TerraformPlanEvidence(
        resource_changes=(
            TerraformResourceChange(
                address="aws_security_group.web",
                resource_type="aws_security_group",
                actions=("update",),
                attributes={"ingress": [{"cidr_blocks": ["0.0.0.0/0"]}]},
            ),
        )
    )
    return ChangeRequest(
        change_id="chg-tf-001",
        repository="org/infra",
        branch="main",
        commit_sha="b" * 40,
        author="dev.two",
        change_type=ChangeType.TERRAFORM_PLAN,
        changed_files=("infra/sg.tf",),
        terraform_plan=plan,
        has_rollback_plan=True,
        planned_maintenance_window=MaintenanceWindow(
            starts_at=datetime.now(UTC), ends_at=datetime.now(UTC) + timedelta(hours=1)
        ),
        environment_target=Environment.PRODUCTION,
        tests_passed=True,
    )


@pytest.fixture
def destructive_migration_change() -> ChangeRequest:
    return ChangeRequest(
        change_id="chg-db-001",
        repository="org/service-b",
        branch="main",
        commit_sha="c" * 40,
        author="dev.three",
        change_type=ChangeType.DB_MIGRATION,
        changed_files=("migrations/0012_drop_legacy.sql",),
        migration_statements=("DROP TABLE legacy_orders;",),
        has_rollback_plan=False,
        environment_target=Environment.PRODUCTION,
        tests_passed=True,
    )


@pytest.fixture
def iam_wildcard_change() -> ChangeRequest:
    return ChangeRequest(
        change_id="chg-iam-001",
        repository="org/infra",
        branch="main",
        commit_sha="d" * 40,
        author="dev.four",
        change_type=ChangeType.IAM_POLICY,
        changed_files=("infra/iam_policy.json",),
        diff='{"Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}]}',
        has_rollback_plan=True,
        environment_target=Environment.PRODUCTION,
        tests_passed=True,
    )
