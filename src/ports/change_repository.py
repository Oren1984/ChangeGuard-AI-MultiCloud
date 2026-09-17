from __future__ import annotations

from typing import Protocol

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.change_record import ChangeRecord
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GatePipelineResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.change_state import ChangeState


class ChangeNotFoundError(Exception):
    pass


class DuplicateChangeError(Exception):
    """Raised when a change_id already exists (idempotent webhook replay)."""


class ChangeRepository(Protocol):
    def create(self, change: ChangeRequest) -> ChangeRecord:
        ...

    def get(self, change_id: str) -> ChangeRecord:
        ...

    def exists(self, change_id: str) -> bool:
        ...

    def list(
        self,
        *,
        state: ChangeState | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ChangeRecord], int]:
        ...

    def update_state(self, change_id: str, new_state: ChangeState) -> ChangeRecord:
        ...

    def attach_risk_assessment(self, change_id: str, assessment: RiskAssessment) -> ChangeRecord:
        ...

    def attach_ai_assessment(
        self, change_id: str, assessment: AIAssessment, *, secondary: bool = False
    ) -> ChangeRecord:
        ...

    def attach_gate_result(self, change_id: str, result: GatePipelineResult) -> ChangeRecord:
        ...

    def attach_routing_decision(self, change_id: str, decision: RoutingDecision) -> ChangeRecord:
        ...
