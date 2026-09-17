from __future__ import annotations

from src.domain.enums.change_state import ChangeState

# Explicit, exhaustive allow-list of state transitions. Anything not listed
# here is forbidden. No API route, repository method, admin action, or AI
# output may bypass this table.
ALLOWED_TRANSITIONS: dict[ChangeState, frozenset[ChangeState]] = {
    ChangeState.PROPOSED: frozenset(
        {ChangeState.RISK_EVALUATED, ChangeState.CANCELLED, ChangeState.BLOCKED}
    ),
    ChangeState.RISK_EVALUATED: frozenset(
        {ChangeState.AI_EVALUATED, ChangeState.CANCELLED, ChangeState.BLOCKED}
    ),
    ChangeState.AI_EVALUATED: frozenset(
        {ChangeState.GATES_PASSED, ChangeState.CANCELLED, ChangeState.BLOCKED}
    ),
    ChangeState.GATES_PASSED: frozenset(
        {
            ChangeState.READY_TO_SHIP,
            ChangeState.CAB_REVIEW_REQUIRED,
            ChangeState.CANCELLED,
            ChangeState.BLOCKED,
        }
    ),
    ChangeState.CAB_REVIEW_REQUIRED: frozenset(
        {ChangeState.CAB_APPROVED, ChangeState.CAB_REJECTED, ChangeState.CANCELLED}
    ),
    ChangeState.CAB_APPROVED: frozenset({ChangeState.READY_TO_SHIP, ChangeState.BLOCKED}),
    ChangeState.CAB_REJECTED: frozenset({ChangeState.BLOCKED}),
    ChangeState.READY_TO_SHIP: frozenset(),
    ChangeState.BLOCKED: frozenset(),
    ChangeState.CANCELLED: frozenset(),
}


class InvalidStateTransitionError(Exception):
    def __init__(self, current: ChangeState, target: ChangeState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"invalid transition: {current.value} -> {target.value}")


def is_transition_allowed(current: ChangeState, target: ChangeState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def validate_transition(current: ChangeState, target: ChangeState) -> None:
    """Fail-closed: raises unless the transition is explicitly allow-listed."""
    if not is_transition_allowed(current, target):
        raise InvalidStateTransitionError(current, target)
