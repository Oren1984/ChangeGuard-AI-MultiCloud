from __future__ import annotations

import pytest

from src.adapters.ai.mock_provider import MockAIProvider
from src.application.evaluation.confidence_gate import ConfidenceThresholds
from src.application.orchestration.evaluation_pipeline import EvaluationPipeline, EvaluationPipelineConfig
from tests.fixtures.fake_repositories import (
    FakeAuditRepository,
    FakeCabRepository,
    FakeChangeRepository,
    FakeKillSwitchRepository,
)


@pytest.fixture
def cab_repo() -> FakeCabRepository:
    return FakeCabRepository()


@pytest.fixture
def change_repo(cab_repo) -> FakeChangeRepository:
    repo = FakeChangeRepository()
    repo.cab_repo = cab_repo  # mirror the SQL adapter's live join of cab_tickets onto changes
    return repo


@pytest.fixture
def audit_repo() -> FakeAuditRepository:
    return FakeAuditRepository()


@pytest.fixture
def kill_switch_repo() -> FakeKillSwitchRepository:
    return FakeKillSwitchRepository()


@pytest.fixture
def build_pipeline(change_repo, cab_repo, audit_repo, kill_switch_repo):
    def _build(**config_overrides) -> EvaluationPipeline:
        config = EvaluationPipelineConfig(
            confidence_thresholds=ConfidenceThresholds(), **config_overrides
        )
        return EvaluationPipeline(
            change_repo=change_repo,
            cab_repo=cab_repo,
            audit_repo=audit_repo,
            kill_switch_repo=kill_switch_repo,
            primary_provider=MockAIProvider(),
            secondary_provider=MockAIProvider(name="mock-ai-v1-secondary", drift=True),
            config=config,
        )

    return _build
