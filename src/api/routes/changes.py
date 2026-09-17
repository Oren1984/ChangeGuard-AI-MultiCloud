from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends, Query, Response, status

from src.api.dependencies.actor import get_actor_context
from src.api.dependencies.repositories import get_change_repo
from src.api.dependencies.use_cases import get_evaluate_change_use_case, get_submit_change_use_case
from src.api.routes._converters import record_to_detail, record_to_summary, request_to_change_request
from src.api.schemas.change_schemas import (
    ChangeDetailResponse,
    ChangeListResponse,
    ChangeSubmitRequest,
)
from src.application.use_cases.evaluate_change import EvaluateChangeUseCase
from src.application.use_cases.submit_change import SubmitChangeUseCase
from src.domain.enums.change_state import ChangeState
from src.security.actor_context import ActorContext

router = APIRouter(prefix="/api/v1/changes", tags=["changes"])


@router.post("", response_model=ChangeDetailResponse)
def submit_change(
    payload: ChangeSubmitRequest,
    response: Response,
    actor: ActorContext = Depends(get_actor_context),
    use_case: SubmitChangeUseCase = Depends(get_submit_change_use_case),
) -> ChangeDetailResponse:
    change = request_to_change_request(payload)
    # The authenticated caller is always the submitter of record for
    # separation-of-duties purposes — a client-supplied `submitted_by`/
    # `author` field must never be able to override who is actually allowed
    # to approve this change later.
    change = dataclasses.replace(change, submitted_by=actor.actor)
    result = use_case.execute(change, actor=actor.actor, actor_role=actor.role.value)
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return record_to_detail(result.record)


@router.get("", response_model=ChangeListResponse)
def list_changes(
    state: ChangeState | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    change_repo=Depends(get_change_repo),
) -> ChangeListResponse:
    records, total = change_repo.list(state=state, limit=limit, offset=offset)
    return ChangeListResponse(
        items=[record_to_summary(r) for r in records], total=total, limit=limit, offset=offset
    )


@router.get("/{change_id}", response_model=ChangeDetailResponse)
def get_change(change_id: str, change_repo=Depends(get_change_repo)) -> ChangeDetailResponse:
    record = change_repo.get(change_id)
    return record_to_detail(record)


@router.post("/{change_id}/evaluate", response_model=ChangeDetailResponse)
def evaluate_change(
    change_id: str,
    actor: ActorContext = Depends(get_actor_context),
    use_case: EvaluateChangeUseCase = Depends(get_evaluate_change_use_case),
) -> ChangeDetailResponse:
    record = use_case.execute(change_id, actor=actor.actor, actor_role=actor.role.value)
    return record_to_detail(record)


@router.get("/{change_id}/cab-brief", response_model=ChangeDetailResponse)
def get_cab_brief(change_id: str, change_repo=Depends(get_change_repo)) -> ChangeDetailResponse:
    record = change_repo.get(change_id)
    return record_to_detail(record)
