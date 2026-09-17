from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums.decision import Decision


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    decision: Decision
    reasons: tuple[str, ...]
    policy_ids: tuple[str, ...] = field(default_factory=tuple)
