from __future__ import annotations

from dataclasses import dataclass

from src.domain.enums.risk_level import RiskLevel


@dataclass(frozen=True, slots=True)
class TriggeredRule:
    rule_id: str
    category: str
    severity: int
    description: str
    evidence: tuple[str, ...] = ()
    required_action: str | None = None


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Output of the deterministic (non-AI) risk engine. Pure and testable."""

    score: int
    level: RiskLevel
    triggered_rules: tuple[TriggeredRule, ...] = ()
    blast_radius: int = 0
    blast_radius_description: str = ""
    required_governance_actions: tuple[str, ...] = ()

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(r.rule_id for r in self.triggered_rules)

    @property
    def has_mandatory_violation(self) -> bool:
        return any(r.severity >= 90 for r in self.triggered_rules)

    def explanations(self) -> tuple[str, ...]:
        return tuple(r.description for r in self.triggered_rules)
