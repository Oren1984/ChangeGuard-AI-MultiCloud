from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_CHANGE_TYPES = Literal[
    "application_code",
    "terraform_plan",
    "helm_k8s_config",
    "db_migration",
    "iam_policy",
    "api_contract",
    "configuration",
]
_ENVIRONMENTS = Literal["dev", "staging", "production"]

MAX_CHANGED_FILES = 2000
MAX_MIGRATION_STATEMENTS = 500
MAX_DEPENDENCIES = 200
MAX_DIFF_CHARS = 500_000


class TerraformResourceChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address: str = Field(min_length=1, max_length=512)
    resource_type: str = Field(min_length=1, max_length=256)
    actions: list[str] = Field(min_length=1, max_length=4)
    attributes: dict[str, Any] = Field(default_factory=dict)


class TerraformPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_changes: list[TerraformResourceChangeRequest] = Field(default_factory=list, max_length=1000)
    raw_plan_json: dict[str, Any] | None = None


class MaintenanceWindowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class ChangeSubmitRequest(BaseModel):
    """Direct, normalized change submission (alternative to the VCS webhook
    intake path). Strict schema: unknown fields are rejected outright."""

    model_config = ConfigDict(extra="forbid")

    change_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.\-]+$")
    repository: str = Field(min_length=1, max_length=512)
    branch: str = Field(min_length=1, max_length=256)
    commit_sha: str = Field(min_length=1, max_length=64)
    author: str = Field(min_length=1, max_length=256)
    change_type: _CHANGE_TYPES
    changed_files: list[str] = Field(default_factory=list, max_length=MAX_CHANGED_FILES)
    diff: str | None = Field(default=None, max_length=MAX_DIFF_CHARS)
    terraform_plan: TerraformPlanRequest | None = None
    migration_statements: list[str] = Field(default_factory=list, max_length=MAX_MIGRATION_STATEMENTS)
    linked_work_item: str | None = Field(default=None, max_length=256)
    planned_maintenance_window: MaintenanceWindowRequest | None = None
    has_rollback_plan: bool = False
    rollback_plan_description: str | None = Field(default=None, max_length=4000)
    service_dependencies: list[str] = Field(default_factory=list, max_length=MAX_DEPENDENCIES)
    environment_target: _ENVIRONMENTS = "dev"
    tests_passed: bool | None = None
    submitted_by: str | None = Field(default=None, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebhookIntakeRequest(BaseModel):
    """Envelope for the simulated GitHub/GitLab webhook intake endpoint."""

    model_config = ConfigDict(extra="allow")  # raw provider payload shape varies; validated by the adapter


class RiskAssessmentResponse(BaseModel):
    score: int
    level: str
    triggered_rules: list[dict[str, Any]]
    blast_radius: int
    blast_radius_description: str
    required_governance_actions: list[str]


class AIAssessmentResponse(BaseModel):
    provider_name: str
    summary: str
    impact_map: list[str]
    dependency_concerns: list[str]
    rollback_considerations: list[str]
    cab_executive_brief: str
    recommended_reviewer_roles: list[str]
    referenced_evidence: list[str]
    recommended_route: str
    suggested_risk_level: str
    confidence: float


class GateResultResponse(BaseModel):
    gate: str
    status: str
    reason: str
    details: dict[str, Any]


class RoutingDecisionResponse(BaseModel):
    decision: str
    reasons: list[str]
    policy_ids: list[str]


class CabTicketResponse(BaseModel):
    ticket_id: str
    change_id: str
    executive_summary: str
    business_impact: str
    technical_impact: str
    risk_level: str
    triggered_controls: list[str]
    evidence: list[str]
    rollback_ready: bool
    maintenance_window_ready: bool
    dependencies: list[str]
    required_approver_roles: list[str]
    submitted_by: str
    created_at: datetime
    decision: str | None
    decision_rationale: str | None
    decided_by: str | None
    decided_role: str | None
    decided_at: datetime | None


class ChangeSummaryResponse(BaseModel):
    change_id: str
    repository: str
    branch: str
    change_type: str
    environment_target: str
    state: str
    risk_level: str | None
    decision: str | None
    created_at: datetime
    updated_at: datetime


class ChangeDetailResponse(BaseModel):
    change_id: str
    repository: str
    branch: str
    commit_sha: str
    author: str
    change_type: str
    changed_files: list[str]
    environment_target: str
    state: str
    created_at: datetime
    updated_at: datetime
    risk_assessment: RiskAssessmentResponse | None
    ai_assessment: AIAssessmentResponse | None
    secondary_ai_assessment: AIAssessmentResponse | None
    gate_results: list[GateResultResponse]
    routing_decision: RoutingDecisionResponse | None
    cab_ticket: CabTicketResponse | None


class ChangeListResponse(BaseModel):
    items: list[ChangeSummaryResponse]
    total: int
    limit: int
    offset: int


class CabDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rationale: str = Field(min_length=1, max_length=4000)
