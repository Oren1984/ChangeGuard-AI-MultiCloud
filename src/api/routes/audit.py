from __future__ import annotations

from fastapi import APIRouter, Depends

from src.api.dependencies.use_cases import get_verify_audit_chain_use_case
from src.api.schemas.admin_schemas import AuditVerificationResponse
from src.application.use_cases.verify_audit_chain import VerifyAuditChainUseCase

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("/verify", response_model=AuditVerificationResponse)
def verify_audit_chain(
    use_case: VerifyAuditChainUseCase = Depends(get_verify_audit_chain_use_case),
) -> AuditVerificationResponse:
    result = use_case.execute()
    return AuditVerificationResponse(
        is_valid=result.is_valid,
        total_records=result.total_records,
        first_invalid_sequence=result.first_invalid_sequence,
        reason=result.reason,
    )
