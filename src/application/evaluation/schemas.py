from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIAssessmentSchema(BaseModel):
    """Strict structural contract an AI provider's output must satisfy.

    This is deliberately re-validated even though AIAssessment is already a
    typed dataclass by the time it reaches Gate 1: dataclasses do not enforce
    value constraints (ranges, enums) at construction time, and a
    misbehaving or malicious provider could otherwise smuggle out-of-range
    values through.
    """

    model_config = ConfigDict(extra="forbid")

    provider_name: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=4000)
    impact_map: list[str]
    dependency_concerns: list[str]
    rollback_considerations: list[str]
    cab_executive_brief: str = Field(max_length=4000)
    recommended_reviewer_roles: list[str]
    referenced_evidence: list[str]
    recommended_route: Literal["AUTO_CLEAR", "CAB_REVIEW_REQUIRED", "HARD_BLOCK"]
    suggested_risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    confidence: float = Field(ge=0.0, le=1.0)
