from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from src.adapters.webhook.dispatcher import normalize_webhook
from src.api.dependencies.actor import get_actor_context
from src.api.dependencies.use_cases import get_submit_change_use_case
from src.api.routes._converters import record_to_detail
from src.api.schemas.change_schemas import ChangeDetailResponse
from src.application.use_cases.submit_change import SubmitChangeUseCase
from src.ports.vcs_provider import VCSNormalizationError
from src.security.actor_context import ActorContext

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/{provider}", response_model=ChangeDetailResponse)
async def receive_webhook(
    provider: str,
    request: Request,
    response: Response,
    actor: ActorContext = Depends(get_actor_context),
    use_case: SubmitChangeUseCase = Depends(get_submit_change_use_case),
) -> ChangeDetailResponse:
    raw_payload = await request.json()
    if not isinstance(raw_payload, dict):
        raise HTTPException(status_code=400, detail="webhook payload must be a JSON object")

    try:
        change = normalize_webhook(provider, raw_payload)
    except VCSNormalizationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = use_case.execute(change, actor=actor.actor, actor_role=actor.role.value)
    # Idempotent replay of an already-known change_id returns 200, a first
    # delivery returns 201 — this is the practical idempotency signal for
    # repeated webhook events described in the API requirements.
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    return record_to_detail(result.record)
