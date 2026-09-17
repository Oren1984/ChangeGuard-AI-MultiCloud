from __future__ import annotations

from src.domain.policies.audit_chain import ChainVerificationResult
from src.ports.audit_repository import AuditRepository


class VerifyAuditChainUseCase:
    def __init__(self, audit_repo: AuditRepository) -> None:
        self._audit_repo = audit_repo

    def execute(self) -> ChainVerificationResult:
        return self._audit_repo.verify_chain()
