from __future__ import annotations

from src.application.routing.decision_router import RoutingContext, route_decision
from src.domain.entities.gate_result import GatePipelineResult, GateResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.enums.decision import Decision
from src.domain.enums.gate_name import GateName, GateStatus
from src.domain.enums.risk_level import RiskLevel


def _all_passed_gates() -> GatePipelineResult:
    return GatePipelineResult(
        results=tuple(
            GateResult(gate=g, status=GateStatus.PASSED, reason="ok") for g in GateName
        )
    )


def test_low_risk_all_gates_passed_auto_clears():
    risk = RiskAssessment(score=0, level=RiskLevel.LOW)
    ctx = RoutingContext(risk=risk, gates=_all_passed_gates(), kill_switch_active=False)
    decision = route_decision(ctx)
    assert decision.decision == Decision.AUTO_CLEAR


def test_critical_risk_hard_blocks():
    risk = RiskAssessment(score=100, level=RiskLevel.CRITICAL)
    ctx = RoutingContext(risk=risk, gates=_all_passed_gates(), kill_switch_active=False)
    decision = route_decision(ctx)
    assert decision.decision == Decision.HARD_BLOCK


def test_high_risk_requires_cab():
    risk = RiskAssessment(score=60, level=RiskLevel.HIGH)
    ctx = RoutingContext(risk=risk, gates=_all_passed_gates(), kill_switch_active=False)
    decision = route_decision(ctx)
    assert decision.decision == Decision.CAB_REVIEW_REQUIRED


def test_failed_gate_hard_blocks_even_at_low_risk():
    risk = RiskAssessment(score=0, level=RiskLevel.LOW)
    gates = GatePipelineResult(
        results=(GateResult(gate=GateName.SAFETY, status=GateStatus.FAILED, reason="unsafe"),)
    )
    ctx = RoutingContext(risk=risk, gates=gates, kill_switch_active=False)
    decision = route_decision(ctx)
    assert decision.decision == Decision.HARD_BLOCK


def test_gate_warning_forces_cab_review():
    risk = RiskAssessment(score=0, level=RiskLevel.LOW)
    gates = GatePipelineResult(
        results=(GateResult(gate=GateName.CONSISTENCY, status=GateStatus.WARNING, reason="mismatch"),)
    )
    ctx = RoutingContext(risk=risk, gates=gates, kill_switch_active=False)
    decision = route_decision(ctx)
    assert decision.decision == Decision.CAB_REVIEW_REQUIRED


def test_kill_switch_blocks_auto_clear():
    risk = RiskAssessment(score=0, level=RiskLevel.LOW)
    ctx = RoutingContext(risk=risk, gates=_all_passed_gates(), kill_switch_active=True)
    decision = route_decision(ctx)
    assert decision.decision == Decision.CAB_REVIEW_REQUIRED


def test_ai_recommendation_cannot_override_hard_block():
    # The router signature never takes an AIAssessment at all — this test
    # documents and locks in that structural guarantee.
    import inspect

    sig = inspect.signature(route_decision)
    assert "ai" not in sig.parameters
    assert list(sig.parameters) == ["ctx"]
