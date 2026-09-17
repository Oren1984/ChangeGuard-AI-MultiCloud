from enum import StrEnum


class ActorRole(StrEnum):
    DEVELOPER = "developer"
    OPERATOR = "operator"
    APPROVER = "approver"
    SECURITY_REVIEWER = "security_reviewer"
    ADMIN = "admin"


# Roles permitted to record a CAB approval/rejection decision.
CAB_DECISION_ROLES = frozenset({ActorRole.APPROVER, ActorRole.SECURITY_REVIEWER, ActorRole.ADMIN})

# Roles permitted to change kill-switch state.
KILL_SWITCH_ROLES = frozenset({ActorRole.ADMIN})
