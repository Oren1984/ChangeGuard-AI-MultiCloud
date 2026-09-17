from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies.actor import get_actor_context
from src.api.dependencies.use_cases import get_kill_switch_use_case
from src.api.schemas.admin_schemas import KillSwitchChangeRequest, KillSwitchStateResponse
from src.application.use_cases.kill_switch import KillSwitchUseCase
from src.security.actor_context import ActorContext

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/kill-switch/activate", response_model=KillSwitchStateResponse)
def activate_kill_switch(
    payload: KillSwitchChangeRequest,
    actor: ActorContext = Depends(get_actor_context),
    use_case: KillSwitchUseCase = Depends(get_kill_switch_use_case),
) -> KillSwitchStateResponse:
    state = use_case.activate(actor=actor.actor, actor_role=actor.role, reason=payload.reason)
    return KillSwitchStateResponse(active=state.active, activated_by=state.activated_by, reason=state.reason)


@router.post("/kill-switch/deactivate", response_model=KillSwitchStateResponse)
def deactivate_kill_switch(
    payload: KillSwitchChangeRequest,
    actor: ActorContext = Depends(get_actor_context),
    use_case: KillSwitchUseCase = Depends(get_kill_switch_use_case),
) -> KillSwitchStateResponse:
    state = use_case.deactivate(actor=actor.actor, actor_role=actor.role, reason=payload.reason)
    return KillSwitchStateResponse(active=state.active, activated_by=state.activated_by, reason=state.reason)
