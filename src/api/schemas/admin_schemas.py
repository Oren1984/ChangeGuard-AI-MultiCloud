from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class KillSwitchChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)


class KillSwitchStateResponse(BaseModel):
    active: bool
    activated_by: str | None
    reason: str | None


class AuditVerificationResponse(BaseModel):
    is_valid: bool
    total_records: int
    first_invalid_sequence: int | None
    reason: str | None


class SystemStatusResponse(BaseModel):
    status: str
    environment: str
    ai_provider: str
    kill_switch_active: bool
    audit_chain_valid: bool
    change_counts_by_state: dict[str, int]
