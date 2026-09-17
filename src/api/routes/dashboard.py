from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.dependencies.repositories import (
    get_audit_repo,
    get_cab_repo,
    get_change_repo,
    get_kill_switch_repo,
)
from src.domain.enums.change_state import ChangeState
from src.domain.enums.risk_level import RiskLevel

router = APIRouter(tags=["dashboard"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    change_repo=Depends(get_change_repo),
    audit_repo=Depends(get_audit_repo),
    cab_repo=Depends(get_cab_repo),
    kill_switch_repo=Depends(get_kill_switch_repo),
) -> HTMLResponse:
    state_counts: dict[str, int] = {}
    for state in ChangeState:
        _, total = change_repo.list(state=state, limit=1)
        state_counts[state.value] = total

    recent_records, _ = change_repo.list(limit=15)

    risk_counts: dict[str, int] = {level.label: 0 for level in RiskLevel}
    for record in recent_records:
        if record.risk_assessment:
            risk_counts[record.risk_assessment.level.label] += 1

    cab_queue, cab_queue_total = cab_repo.list_queue(limit=10)
    verification = audit_repo.verify_chain()
    kill_switch_state = kill_switch_repo.get_state()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "state_counts": state_counts,
            "risk_counts": risk_counts,
            "recent_records": recent_records,
            "cab_queue": cab_queue,
            "cab_queue_total": cab_queue_total,
            "verification": verification,
            "kill_switch_state": kill_switch_state,
        },
    )
