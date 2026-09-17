from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.adapters.ai.mock_provider import MockAIProvider
from src.api.dependencies.providers import get_primary_ai_provider, get_secondary_ai_provider
from src.api.dependencies.repositories import (
    get_audit_repo,
    get_cab_repo,
    get_change_repo,
    get_kill_switch_repo,
)
from src.main import create_app
from tests.fixtures.fake_repositories import (
    FakeAuditRepository,
    FakeCabRepository,
    FakeChangeRepository,
    FakeKillSwitchRepository,
)


@pytest.fixture
def fakes():
    change_repo = FakeChangeRepository()
    cab_repo = FakeCabRepository()
    change_repo.cab_repo = cab_repo  # mirror the SQL adapter's live join of cab_tickets onto changes
    return {
        "change_repo": change_repo,
        "cab_repo": cab_repo,
        "audit_repo": FakeAuditRepository(),
        "kill_switch_repo": FakeKillSwitchRepository(),
    }


@pytest.fixture
def client(fakes):
    app = create_app()
    app.dependency_overrides[get_change_repo] = lambda: fakes["change_repo"]
    app.dependency_overrides[get_cab_repo] = lambda: fakes["cab_repo"]
    app.dependency_overrides[get_audit_repo] = lambda: fakes["audit_repo"]
    app.dependency_overrides[get_kill_switch_repo] = lambda: fakes["kill_switch_repo"]
    app.dependency_overrides[get_primary_ai_provider] = lambda: MockAIProvider()
    app.dependency_overrides[get_secondary_ai_provider] = lambda: MockAIProvider(
        name="mock-ai-v1-secondary", drift=True
    )
    # Deliberately not used as a context manager: that would trigger the
    # app's startup lifespan event, which seeds the kill-switch default via
    # a real database session — unwanted/unavailable in these DB-free tests.
    yield TestClient(app)


def actor_headers(actor: str, role: str) -> dict:
    return {"X-ChangeGuard-Actor": actor, "X-ChangeGuard-Role": role}


VALID_CHANGE_PAYLOAD = {
    "change_id": "chg-sec-001",
    "repository": "org/service-a",
    "branch": "main",
    "commit_sha": "a" * 40,
    "author": "dev.one",
    "change_type": "application_code",
    "changed_files": ["src/app.py"],
    "has_rollback_plan": True,
    "environment_target": "staging",
    "tests_passed": True,
}
