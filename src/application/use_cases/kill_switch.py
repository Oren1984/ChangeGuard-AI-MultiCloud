from __future__ import annotations

from src.domain.enums.actor_role import ActorRole
from src.domain.policies.kill_switch_policy import KillSwitchState, can_change_kill_switch
from src.ports.audit_repository import AuditRepository
from src.ports.kill_switch_repository import KillSwitchRepository


class UnauthorizedKillSwitchChangeError(Exception):
    pass


class KillSwitchUseCase:
    def __init__(self, kill_switch_repo: KillSwitchRepository, audit_repo: AuditRepository) -> None:
        self._kill_switch_repo = kill_switch_repo
        self._audit_repo = audit_repo

    def activate(self, *, actor: str, actor_role: ActorRole, reason: str) -> KillSwitchState:
        return self._set(True, actor=actor, actor_role=actor_role, reason=reason)

    def deactivate(self, *, actor: str, actor_role: ActorRole, reason: str) -> KillSwitchState:
        return self._set(False, actor=actor, actor_role=actor_role, reason=reason)

    def _set(self, active: bool, *, actor: str, actor_role: ActorRole, reason: str) -> KillSwitchState:
        allowed, error = can_change_kill_switch(actor_role)
        if not allowed:
            raise UnauthorizedKillSwitchChangeError(error)

        state = self._kill_switch_repo.set_state(
            KillSwitchState(active=active, activated_by=actor, reason=reason)
        )
        self._audit_repo.append(
            actor=actor,
            actor_role=actor_role.value,
            action="KILL_SWITCH_ACTIVATED" if active else "KILL_SWITCH_DEACTIVATED",
            entity_id="kill_switch",
            payload={"reason": reason},
        )
        return state
