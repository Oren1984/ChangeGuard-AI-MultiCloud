from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums.risk_level import RiskLevel


@dataclass(frozen=True, slots=True)
class AIAssessment:
    """Advisory-only AI output. Treated as untrusted until it passes all five
    assurance gates. Must never be granted authority to approve, merge, or
    execute anything on its own.
    """

    provider_name: str
    summary: str
    impact_map: tuple[str, ...]
    dependency_concerns: tuple[str, ...]
    rollback_considerations: tuple[str, ...]
    cab_executive_brief: str
    recommended_reviewer_roles: tuple[str, ...]
    referenced_evidence: tuple[str, ...]
    recommended_route: str  # advisory only — "AUTO_CLEAR" | "CAB_REVIEW_REQUIRED" | "HARD_BLOCK"
    suggested_risk_level: RiskLevel
    confidence: float  # 0.0 - 1.0
    raw_response: dict = field(default_factory=dict)
