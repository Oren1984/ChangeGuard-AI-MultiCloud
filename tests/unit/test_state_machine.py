from __future__ import annotations

import pytest

from src.domain.enums.change_state import ChangeState
from src.domain.state_machine.transitions import (
    InvalidStateTransitionError,
    is_transition_allowed,
    validate_transition,
)


def test_happy_path_auto_clear_sequence():
    sequence = [
        ChangeState.PROPOSED,
        ChangeState.RISK_EVALUATED,
        ChangeState.AI_EVALUATED,
        ChangeState.GATES_PASSED,
        ChangeState.READY_TO_SHIP,
    ]
    for current, nxt in zip(sequence, sequence[1:], strict=False):
        validate_transition(current, nxt)


def test_cab_path_sequence():
    sequence = [
        ChangeState.PROPOSED,
        ChangeState.RISK_EVALUATED,
        ChangeState.AI_EVALUATED,
        ChangeState.GATES_PASSED,
        ChangeState.CAB_REVIEW_REQUIRED,
        ChangeState.CAB_APPROVED,
        ChangeState.READY_TO_SHIP,
    ]
    for current, nxt in zip(sequence, sequence[1:], strict=False):
        validate_transition(current, nxt)


def test_terminal_states_have_no_outgoing_transitions():
    for terminal in (ChangeState.READY_TO_SHIP, ChangeState.BLOCKED, ChangeState.CANCELLED):
        for target in ChangeState:
            assert not is_transition_allowed(terminal, target)


def test_cannot_skip_states():
    assert not is_transition_allowed(ChangeState.PROPOSED, ChangeState.GATES_PASSED)
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(ChangeState.PROPOSED, ChangeState.READY_TO_SHIP)


def test_cab_rejected_leads_only_to_blocked():
    assert is_transition_allowed(ChangeState.CAB_REJECTED, ChangeState.BLOCKED)
    assert not is_transition_allowed(ChangeState.CAB_REJECTED, ChangeState.READY_TO_SHIP)
