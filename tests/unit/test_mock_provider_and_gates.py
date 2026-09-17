from __future__ import annotations

import dataclasses

from src.adapters.ai.mock_provider import MockAIProvider
from src.application.evaluation.gate_pipeline import run_gate_pipeline
from src.domain.enums.gate_name import GateStatus


def test_default_mock_provider_output_passes_all_gates(low_risk_app_change):
    primary = MockAIProvider()
    secondary = MockAIProvider(name="mock-ai-v1-secondary", drift=True)
    p = primary.analyze(low_risk_app_change)
    s = secondary.analyze(low_risk_app_change)
    result = run_gate_pipeline(primary=p, change=low_risk_app_change, secondary=s)
    assert result.all_passed, [r.reason for r in result.results]


def test_fabricated_evidence_fails_grounding_gate(low_risk_app_change):
    change = dataclasses.replace(low_risk_app_change, metadata={"_demo": "fabricated_evidence"})
    provider = MockAIProvider()
    assessment = provider.analyze(change)
    result = run_gate_pipeline(primary=assessment, change=change)
    grounding = [r for r in result.results if r.gate.value == "grounding"][0]
    assert grounding.status == GateStatus.FAILED
    assert result.any_failed


def test_low_confidence_fails_confidence_gate(low_risk_app_change):
    change = dataclasses.replace(low_risk_app_change, metadata={"_demo": "low_confidence"})
    provider = MockAIProvider()
    assessment = provider.analyze(change)
    result = run_gate_pipeline(primary=assessment, change=change)
    confidence = [r for r in result.results if r.gate.value == "confidence"][0]
    assert confidence.status == GateStatus.FAILED


def test_dangerous_recommendation_fails_safety_gate(low_risk_app_change):
    change = dataclasses.replace(low_risk_app_change, metadata={"_demo": "dangerous_recommendation"})
    provider = MockAIProvider()
    assessment = provider.analyze(change)
    result = run_gate_pipeline(primary=assessment, change=change)
    safety = [r for r in result.results if r.gate.value == "safety"][0]
    assert safety.status == GateStatus.FAILED


def test_inconsistent_secondary_opinion_triggers_warning(low_risk_app_change):
    change = dataclasses.replace(low_risk_app_change, metadata={"_demo": "inconsistent"})
    primary_provider = MockAIProvider()
    secondary_provider = MockAIProvider(name="mock-ai-v1-secondary", drift=True)
    primary = primary_provider.analyze(change)
    secondary = secondary_provider.analyze(change)
    result = run_gate_pipeline(primary=primary, change=change, secondary=secondary)
    consistency = [r for r in result.results if r.gate.value == "consistency"][0]
    assert consistency.status == GateStatus.WARNING
    assert result.any_warning
    assert not result.any_failed
