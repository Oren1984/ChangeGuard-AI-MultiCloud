from __future__ import annotations

from typing import Protocol

from src.domain.policies.kill_switch_policy import KillSwitchState


class KillSwitchRepository(Protocol):
    def get_state(self) -> KillSwitchState:
        ...

    def set_state(self, state: KillSwitchState) -> KillSwitchState:
        ...
