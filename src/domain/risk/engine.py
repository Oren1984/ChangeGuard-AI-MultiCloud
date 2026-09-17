"""Deterministic change-risk engine. No AI, no I/O, fully pure and unit-testable."""

from __future__ import annotations

from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.risk_assessment import RiskAssessment, TriggeredRule
from src.domain.enums.risk_level import RiskLevel
from src.domain.risk.rules import RULE_REGISTRY, RuleFn

MANDATORY_SEVERITY_FLOOR = 90

_LEVEL_THRESHOLDS: tuple[tuple[int, RiskLevel], ...] = (
    (80, RiskLevel.CRITICAL),
    (50, RiskLevel.HIGH),
    (25, RiskLevel.MEDIUM),
    (0, RiskLevel.LOW),
)


def _score_to_level(score: int, has_mandatory_violation: bool) -> RiskLevel:
    if has_mandatory_violation:
        return RiskLevel.CRITICAL
    for floor, level in _LEVEL_THRESHOLDS:
        if score >= floor:
            return level
    return RiskLevel.LOW


def evaluate_risk(
    change: ChangeRequest, rules: tuple[RuleFn, ...] = RULE_REGISTRY
) -> RiskAssessment:
    triggered: list[TriggeredRule] = []
    for rule in rules:
        outcome = rule(change)
        if outcome is not None:
            triggered.append(outcome)

    raw_score = sum(r.severity for r in triggered)
    score = min(100, raw_score)
    has_mandatory = any(r.severity >= MANDATORY_SEVERITY_FLOOR for r in triggered)
    level = _score_to_level(score, has_mandatory)

    blast_radius = change.dependency_count
    if blast_radius == 0:
        blast_description = "No declared service dependencies; blast radius limited to this component."
    elif blast_radius <= 2:
        blast_description = f"Limited blast radius: {blast_radius} dependent service(s)."
    else:
        blast_description = f"Wide blast radius: {blast_radius} dependent services potentially affected."

    governance_actions: list[str] = []
    seen: set[str] = set()
    for r in triggered:
        if r.required_action and r.required_action not in seen:
            governance_actions.append(r.required_action)
            seen.add(r.required_action)
    if level in (RiskLevel.HIGH, RiskLevel.CRITICAL) and "CAB review is required." not in seen:
        governance_actions.append("CAB review is required.")

    return RiskAssessment(
        score=score,
        level=level,
        triggered_rules=tuple(triggered),
        blast_radius=blast_radius,
        blast_radius_description=blast_description,
        required_governance_actions=tuple(governance_actions),
    )
