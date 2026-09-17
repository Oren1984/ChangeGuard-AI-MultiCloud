from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.enums.gate_name import GateName, GateStatus


@dataclass(frozen=True, slots=True)
class GateResult:
    gate: GateName
    status: GateStatus
    reason: str
    details: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == GateStatus.PASSED

    @property
    def failed(self) -> bool:
        return self.status == GateStatus.FAILED


@dataclass(frozen=True, slots=True)
class GatePipelineResult:
    results: tuple[GateResult, ...]

    @property
    def all_passed(self) -> bool:
        return all(r.status == GateStatus.PASSED for r in self.results)

    @property
    def any_failed(self) -> bool:
        return any(r.status == GateStatus.FAILED for r in self.results)

    @property
    def any_warning(self) -> bool:
        return any(r.status == GateStatus.WARNING for r in self.results)

    def get(self, gate: GateName) -> GateResult | None:
        for r in self.results:
            if r.gate == gate:
                return r
        return None
