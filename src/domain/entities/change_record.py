from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.entities.ai_assessment import AIAssessment
from src.domain.entities.cab_ticket import CabTicket
from src.domain.entities.change_request import ChangeRequest
from src.domain.entities.gate_result import GatePipelineResult
from src.domain.entities.risk_assessment import RiskAssessment
from src.domain.entities.routing_decision import RoutingDecision
from src.domain.enums.change_state import ChangeState


@dataclass(frozen=True, slots=True)
class ChangeRecord:
    """Aggregate root persisted and returned by the ChangeRepository: the
    normalized change plus every evaluation artifact produced for it."""

    change: ChangeRequest
    state: ChangeState
    created_at: datetime
    updated_at: datetime
    risk_assessment: RiskAssessment | None = None
    ai_assessment: AIAssessment | None = None
    secondary_ai_assessment: AIAssessment | None = None
    gate_result: GatePipelineResult | None = None
    routing_decision: RoutingDecision | None = None
    cab_ticket: CabTicket | None = None

    def with_updates(self, **changes) -> ChangeRecord:
        import dataclasses

        return dataclasses.replace(self, **changes)
