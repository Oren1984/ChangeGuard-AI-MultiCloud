from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies.actor import get_actor_context
from src.api.dependencies.use_cases import get_cab_decision_use_case
from src.api.routes._converters import record_to_detail
from src.api.schemas.change_schemas import CabDecisionRequest, ChangeDetailResponse
from src.application.use_cases.cab_decision import CabDecisionUseCase
from src.security.actor_context import ActorContext

router = APIRouter(prefix="/api/v1/changes", tags=["cab"])


@router.post("/{change_id}/cab/approve", response_model=ChangeDetailResponse)
def approve_change(
    change_id: str,
    payload: CabDecisionRequest,
    actor: ActorContext = Depends(get_actor_context),
    use_case: CabDecisionUseCase = Depends(get_cab_decision_use_case),
) -> ChangeDetailResponse:
    record = use_case.execute(
        change_id, approve=True, rationale=payload.rationale, actor=actor.actor, actor_role=actor.role
    )
    return record_to_detail(record)


@router.post("/{change_id}/cab/reject", response_model=ChangeDetailResponse)
def reject_change(
    change_id: str,
    payload: CabDecisionRequest,
    actor: ActorContext = Depends(get_actor_context),
    use_case: CabDecisionUseCase = Depends(get_cab_decision_use_case),
) -> ChangeDetailResponse:
    record = use_case.execute(
        change_id, approve=False, rationale=payload.rationale, actor=actor.actor, actor_role=actor.role
    )
    return record_to_detail(record)
