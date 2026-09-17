from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.api.dependencies.db import get_db
from src.observability.metrics import render_latest

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(session: Session = Depends(get_db)) -> dict:
    session.execute(text("SELECT 1"))
    return {"status": "ready"}


@router.get("/metrics")
def metrics() -> Response:
    payload, content_type = render_latest()
    return Response(content=payload, media_type=content_type)
