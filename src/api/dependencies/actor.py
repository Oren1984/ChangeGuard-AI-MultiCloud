from __future__ import annotations

from fastapi import Header, HTTPException

from src.security.actor_context import ActorContext, InvalidActorContextError, parse_actor_context


def get_actor_context(
    x_changeguard_actor: str | None = Header(default=None, alias="X-ChangeGuard-Actor"),
    x_changeguard_role: str | None = Header(default=None, alias="X-ChangeGuard-Role"),
) -> ActorContext:
    try:
        return parse_actor_context(x_changeguard_actor, x_changeguard_role)
    except InvalidActorContextError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
