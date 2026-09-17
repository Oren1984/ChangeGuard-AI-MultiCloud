"""Header-based actor identity for the POC.

This is an explicit, documented POC boundary — not production-grade
identity. It trusts two request headers as-is:

    X-ChangeGuard-Actor: a free-text but length- and charset-limited actor id
    X-ChangeGuard-Role:  one of ActorRole's values

Production hardening (OIDC/OAuth2, enterprise IdP, signed tokens, mTLS) is
documented in docs/TRADEOFFS_AND_PRODUCTION_ROADMAP.md and must not be
implemented as an afterthought bolted onto this header scheme.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.enums.actor_role import ActorRole

ACTOR_HEADER = "X-ChangeGuard-Actor"
ROLE_HEADER = "X-ChangeGuard-Role"

_ACTOR_PATTERN = re.compile(r"^[A-Za-z0-9_.\-@]{1,128}$")


class InvalidActorContextError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ActorContext:
    actor: str
    role: ActorRole


def parse_actor_context(actor_header: str | None, role_header: str | None) -> ActorContext:
    if not actor_header or not role_header:
        raise InvalidActorContextError(f"both {ACTOR_HEADER} and {ROLE_HEADER} headers are required")
    if not _ACTOR_PATTERN.match(actor_header):
        raise InvalidActorContextError(f"{ACTOR_HEADER} contains invalid characters or is too long")
    try:
        role = ActorRole(role_header.strip().lower())
    except ValueError as exc:
        valid = ", ".join(r.value for r in ActorRole)
        raise InvalidActorContextError(f"{ROLE_HEADER} must be one of: {valid}") from exc
    return ActorContext(actor=actor_header, role=role)
