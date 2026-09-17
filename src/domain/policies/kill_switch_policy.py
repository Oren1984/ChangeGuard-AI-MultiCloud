"""Kill-switch fail-closed policy.

The kill switch is checked twice in the pipeline (before calling the AI
provider, and again immediately before final routing) so a state change
mid-evaluation can never slip an AI-assisted change through to AUTO_CLEAR.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.enums.actor_role import ActorRole


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    active: bool
    activated_by: str | None = None
    reason: str | None = None


def can_change_kill_switch(role: ActorRole) -> tuple[bool, str]:
    if role != ActorRole.ADMIN:
        return False, "only the admin role may change kill-switch state"
    return True, ""


def blocks_auto_clear(state: KillSwitchState) -> bool:
    """While active, no AI-assisted change may be auto-cleared. Deterministic
    risk evaluation may still run and be recorded."""
    return state.active
