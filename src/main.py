from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import admin, audit, cab, changes, dashboard, health, system, webhooks
from src.application.orchestration.evaluation_pipeline import PipelineFailureError
from src.application.use_cases.cab_decision import NoCabTicketError, SeparationOfDutiesViolationError
from src.application.use_cases.kill_switch import UnauthorizedKillSwitchChangeError
from src.config import get_settings
from src.domain.state_machine.transitions import InvalidStateTransitionError
from src.observability.correlation import CORRELATION_HEADER, new_correlation_id, set_correlation_id
from src.observability.logging import configure_logging
from src.observability.metrics import http_errors_total
from src.ports.ai_provider import AIProviderError
from src.ports.audit_repository import AuditPersistenceError
from src.ports.cab_repository import CabTicketNotFoundError
from src.ports.change_repository import ChangeNotFoundError, DuplicateChangeError
from src.ports.vcs_provider import VCSNormalizationError
from src.security.redaction import redact_value

_STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

_ERROR_STATUS_MAP: dict[type[Exception], int] = {
    ChangeNotFoundError: status.HTTP_404_NOT_FOUND,
    CabTicketNotFoundError: status.HTTP_404_NOT_FOUND,
    NoCabTicketError: status.HTTP_404_NOT_FOUND,
    DuplicateChangeError: status.HTTP_409_CONFLICT,
    InvalidStateTransitionError: status.HTTP_409_CONFLICT,
    SeparationOfDutiesViolationError: status.HTTP_403_FORBIDDEN,
    UnauthorizedKillSwitchChangeError: status.HTTP_403_FORBIDDEN,
    VCSNormalizationError: status.HTTP_400_BAD_REQUEST,
    AIProviderError: status.HTTP_503_SERVICE_UNAVAILABLE,
    PipelineFailureError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    AuditPersistenceError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}


def _seed_kill_switch_default(settings) -> None:
    from src.adapters.persistence.kill_switch_repository_sqlalchemy import SqlAlchemyKillSwitchRepository
    from src.adapters.persistence.models import KillSwitchStateORM
    from src.adapters.persistence.session import get_sessionmaker
    from src.domain.policies.kill_switch_policy import KillSwitchState

    session = get_sessionmaker(settings.database_url)()
    try:
        if session.get(KillSwitchStateORM, 1) is None:
            SqlAlchemyKillSwitchRepository(session).set_state(
                KillSwitchState(active=settings.kill_switch_default_active, reason="startup default")
            )
    finally:
        session.close()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        _seed_kill_switch_default(settings)
        yield

    app = FastAPI(
        title="ChangeGuard AI MultiCloud",
        description="Autonomous Change Risk & Release Governance POC",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def correlation_and_size_guard(request: Request, call_next):
        correlation_id = request.headers.get(CORRELATION_HEADER) or new_correlation_id()
        set_correlation_id(correlation_id)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_payload_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "error": "payload_too_large",
                    "detail": f"payload exceeds the {settings.max_payload_bytes} byte limit",
                    "correlation_id": correlation_id,
                },
            )

        response: Response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    for exc_type, status_code in _ERROR_STATUS_MAP.items():

        def _make_handler(code: int):
            async def _handler(request: Request, exc: Exception) -> JSONResponse:
                http_errors_total.labels(status_code=str(code)).inc()
                return JSONResponse(
                    status_code=code,
                    content={
                        "error": type(exc).__name__,
                        "detail": redact_value(str(exc)),
                        "correlation_id": request.headers.get(CORRELATION_HEADER, ""),
                    },
                )

            return _handler

        app.add_exception_handler(exc_type, _make_handler(status_code))

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Fail closed and never leak stack traces or internals to clients.
        http_errors_total.labels(status_code="500").inc()
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "detail": "an unexpected error occurred",
                "correlation_id": request.headers.get(CORRELATION_HEADER, ""),
            },
        )

    app.include_router(health.router)
    app.include_router(changes.router)
    app.include_router(cab.router)
    app.include_router(admin.router)
    app.include_router(audit.router)
    app.include_router(system.router)
    app.include_router(webhooks.router)
    app.include_router(dashboard.router)

    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


app = create_app()
