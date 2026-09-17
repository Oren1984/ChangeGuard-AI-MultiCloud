from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies.repositories import get_audit_repo, get_change_repo, get_kill_switch_repo
from src.api.schemas.admin_schemas import SystemStatusResponse
from src.config import Settings, get_settings
from src.domain.enums.change_state import ChangeState

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse)
def system_status(
    change_repo=Depends(get_change_repo),
    audit_repo=Depends(get_audit_repo),
    kill_switch_repo=Depends(get_kill_switch_repo),
    settings: Settings = Depends(get_settings),
) -> SystemStatusResponse:
    counts: dict[str, int] = {}
    for state in ChangeState:
        _, total = change_repo.list(state=state, limit=1, offset=0)
        counts[state.value] = total

    verification = audit_repo.verify_chain()
    kill_switch_state = kill_switch_repo.get_state()

    return SystemStatusResponse(
        status="ok",
        environment=settings.environment,
        ai_provider=settings.ai_provider,
        kill_switch_active=kill_switch_state.active,
        audit_chain_valid=verification.is_valid,
        change_counts_by_state=counts,
    )
