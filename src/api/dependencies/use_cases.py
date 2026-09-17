from __future__ import annotations

from fastapi import Depends

from src.api.dependencies.providers import get_primary_ai_provider, get_secondary_ai_provider
from src.api.dependencies.repositories import (
    get_audit_repo,
    get_cab_repo,
    get_change_repo,
    get_kill_switch_repo,
)
from src.application.evaluation.confidence_gate import ConfidenceThresholds
from src.application.orchestration.evaluation_pipeline import EvaluationPipeline, EvaluationPipelineConfig
from src.application.use_cases.cab_decision import CabDecisionUseCase
from src.application.use_cases.evaluate_change import EvaluateChangeUseCase
from src.application.use_cases.kill_switch import KillSwitchUseCase
from src.application.use_cases.submit_change import SubmitChangeUseCase
from src.application.use_cases.verify_audit_chain import VerifyAuditChainUseCase
from src.config import Settings, get_settings
from src.ports.ai_provider import AIProvider
from src.ports.audit_repository import AuditRepository
from src.ports.cab_repository import CabRepository
from src.ports.change_repository import ChangeRepository
from src.ports.kill_switch_repository import KillSwitchRepository


def get_submit_change_use_case(
    change_repo: ChangeRepository = Depends(get_change_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> SubmitChangeUseCase:
    return SubmitChangeUseCase(change_repo, audit_repo)


def get_evaluate_change_use_case(
    change_repo: ChangeRepository = Depends(get_change_repo),
    cab_repo: CabRepository = Depends(get_cab_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
    kill_switch_repo: KillSwitchRepository = Depends(get_kill_switch_repo),
    primary_provider: AIProvider = Depends(get_primary_ai_provider),
    secondary_provider: AIProvider = Depends(get_secondary_ai_provider),
    settings: Settings = Depends(get_settings),
) -> EvaluateChangeUseCase:
    pipeline = EvaluationPipeline(
        change_repo=change_repo,
        cab_repo=cab_repo,
        audit_repo=audit_repo,
        kill_switch_repo=kill_switch_repo,
        primary_provider=primary_provider,
        secondary_provider=secondary_provider,
        config=EvaluationPipelineConfig(
            confidence_thresholds=ConfidenceThresholds(
                approval_threshold=settings.confidence_approval_threshold,
                hard_floor=settings.confidence_hard_floor,
            ),
            allow_critical_cab_exception=settings.allow_critical_cab_exception,
        ),
    )
    return EvaluateChangeUseCase(pipeline)


def get_cab_decision_use_case(
    change_repo: ChangeRepository = Depends(get_change_repo),
    cab_repo: CabRepository = Depends(get_cab_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> CabDecisionUseCase:
    return CabDecisionUseCase(change_repo, cab_repo, audit_repo)


def get_kill_switch_use_case(
    kill_switch_repo: KillSwitchRepository = Depends(get_kill_switch_repo),
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> KillSwitchUseCase:
    return KillSwitchUseCase(kill_switch_repo, audit_repo)


def get_verify_audit_chain_use_case(
    audit_repo: AuditRepository = Depends(get_audit_repo),
) -> VerifyAuditChainUseCase:
    return VerifyAuditChainUseCase(audit_repo)
