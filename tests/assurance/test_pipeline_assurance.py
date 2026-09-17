from __future__ import annotations

import pytest

from src.application.orchestration.evaluation_pipeline import PipelineFailureError
from src.domain.enums.change_state import ChangeState
from src.domain.enums.decision import Decision
from src.domain.enums.gate_name import GateName
from src.domain.policies.kill_switch_policy import KillSwitchState
from tests.fixtures.builders import make_change_request


def _submit(change_repo, **overrides):
    change = make_change_request(**overrides)
    change_repo.create(change)
    return change


def test_happy_path_auto_clears(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-happy")
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-happy", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.READY_TO_SHIP
    assert record.routing_decision.decision == Decision.AUTO_CLEAR
    assert record.gate_result.all_passed


def test_fabricated_evidence_hard_blocks(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-fab", metadata={"_demo": "fabricated_evidence"})
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-fab", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.BLOCKED
    assert record.routing_decision.decision == Decision.HARD_BLOCK
    grounding = record.gate_result.get(GateName.GROUNDING)
    assert grounding.status.value == "FAILED"


def test_low_confidence_hard_blocks(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-lowconf", metadata={"_demo": "low_confidence"})
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-lowconf", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.BLOCKED
    assert record.routing_decision.decision == Decision.HARD_BLOCK


def test_warning_confidence_requires_cab_review(change_repo, cab_repo, build_pipeline):
    _submit(change_repo, change_id="chg-warnconf", metadata={"_demo": "warning_confidence"})
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-warnconf", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.CAB_REVIEW_REQUIRED
    assert record.routing_decision.decision == Decision.CAB_REVIEW_REQUIRED
    assert cab_repo.get_ticket_for_change("chg-warnconf") is not None


def test_dangerous_recommendation_hard_blocks(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-danger", metadata={"_demo": "dangerous_recommendation"})
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-danger", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.BLOCKED
    assert record.routing_decision.decision == Decision.HARD_BLOCK


def test_inconsistent_ai_opinions_require_cab_review(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-inconsistent", metadata={"_demo": "inconsistent"})
    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-inconsistent", actor="ci-bot", actor_role="developer")
    assert record.state == ChangeState.CAB_REVIEW_REQUIRED
    assert record.routing_decision.decision == Decision.CAB_REVIEW_REQUIRED


def test_primary_provider_unavailable_fails_closed(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-unavailable", metadata={"_demo": "provider_unavailable"})
    pipeline = build_pipeline()
    with pytest.raises(PipelineFailureError):
        pipeline.evaluate("chg-unavailable", actor="ci-bot", actor_role="developer")
    assert change_repo.get("chg-unavailable").state == ChangeState.BLOCKED


def test_primary_provider_timeout_fails_closed(change_repo, build_pipeline):
    _submit(change_repo, change_id="chg-timeout", metadata={"_demo": "provider_timeout"})
    pipeline = build_pipeline()
    with pytest.raises(PipelineFailureError):
        pipeline.evaluate("chg-timeout", actor="ci-bot", actor_role="developer")
    assert change_repo.get("chg-timeout").state == ChangeState.BLOCKED


def test_kill_switch_activated_between_stages_blocks_auto_clear(
    change_repo, build_pipeline, kill_switch_repo
):
    _submit(change_repo, change_id="chg-killswitch")

    # Flip the switch after the pipeline's first (pre-AI) check but before
    # its second (pre-routing) check — the mandatory second check must catch it.
    original_get_state = kill_switch_repo.get_state
    call_count = {"n": 0}

    def toggling_get_state():
        call_count["n"] += 1
        if call_count["n"] >= 2:
            kill_switch_repo.set_state(
                KillSwitchState(active=True, reason="simulated mid-flight activation")
            )
        return original_get_state()

    kill_switch_repo.get_state = toggling_get_state  # type: ignore[method-assign]

    pipeline = build_pipeline()
    record = pipeline.evaluate("chg-killswitch", actor="ci-bot", actor_role="developer")

    assert record.routing_decision.decision == Decision.CAB_REVIEW_REQUIRED
    assert record.state == ChangeState.CAB_REVIEW_REQUIRED


def test_secondary_provider_failure_is_non_fatal_and_skips_consistency_gate(
    change_repo, build_pipeline, audit_repo
):
    from src.adapters.ai.mock_provider import MockAIProvider
    from src.application.evaluation.confidence_gate import ConfidenceThresholds
    from src.application.orchestration.evaluation_pipeline import (
        EvaluationPipeline,
        EvaluationPipelineConfig,
    )
    from tests.fixtures.fake_repositories import FakeCabRepository, FakeKillSwitchRepository

    _submit(change_repo, change_id="chg-secondary-down")

    class AlwaysFailsSecondary:
        name = "broken-secondary"

        def analyze(self, change):
            from src.ports.ai_provider import AIProviderError

            raise AIProviderError("secondary down")

    pipeline = EvaluationPipeline(
        change_repo=change_repo,
        cab_repo=FakeCabRepository(),
        audit_repo=audit_repo,
        kill_switch_repo=FakeKillSwitchRepository(),
        primary_provider=MockAIProvider(),
        secondary_provider=AlwaysFailsSecondary(),
        config=EvaluationPipelineConfig(confidence_thresholds=ConfidenceThresholds()),
    )
    record = pipeline.evaluate("chg-secondary-down", actor="ci-bot", actor_role="developer")

    consistency = record.gate_result.get(GateName.CONSISTENCY)
    assert consistency.status.value == "SKIPPED"
    assert record.state == ChangeState.READY_TO_SHIP
