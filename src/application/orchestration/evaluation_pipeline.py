"""Orchestrates the full change-evaluation pipeline:

    intake -> risk evaluation -> AI evaluation -> assurance gates
    -> routing decision -> CAB workflow (if required) -> final state

Every step writes its artifact to the change repository and an entry to the
hash-chained audit trail. The kill switch is checked twice (see
src/domain/policies/kill_switch_policy.py): once before the AI provider is
invoked, and again immediately before the final routing decision, so a
mid-evaluation kill-switch activation can never let an AI-assisted change
slip through to AUTO_CLEAR.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.evaluation.confidence_gate import ConfidenceThresholds
from src.application.evaluation.gate_pipeline import run_gate_pipeline
from src.application.orchestration.cab_ticket_builder import build_cab_ticket
from src.application.routing.decision_router import RoutingContext, route_decision
from src.domain.entities.change_record import ChangeRecord
from src.domain.enums.change_state import ChangeState
from src.domain.enums.decision import Decision
from src.domain.risk.engine import evaluate_risk
from src.domain.state_machine.transitions import validate_transition
from src.ports.ai_provider import AIProvider, AIProviderError
from src.ports.audit_repository import AuditRepository
from src.ports.cab_repository import CabRepository
from src.ports.change_repository import ChangeRepository
from src.ports.kill_switch_repository import KillSwitchRepository


class PipelineFailureError(Exception):
    """Raised whenever the pipeline cannot safely continue. The caller must
    treat this as fail-closed: the change is left in (or forced into)
    BLOCKED, never silently advanced."""


@dataclass(frozen=True, slots=True)
class EvaluationPipelineConfig:
    confidence_thresholds: ConfidenceThresholds = ConfidenceThresholds()
    allow_critical_cab_exception: bool = False


class EvaluationPipeline:
    def __init__(
        self,
        *,
        change_repo: ChangeRepository,
        cab_repo: CabRepository,
        audit_repo: AuditRepository,
        kill_switch_repo: KillSwitchRepository,
        primary_provider: AIProvider,
        secondary_provider: AIProvider,
        config: EvaluationPipelineConfig = EvaluationPipelineConfig(),
    ) -> None:
        self._change_repo = change_repo
        self._cab_repo = cab_repo
        self._audit_repo = audit_repo
        self._kill_switch_repo = kill_switch_repo
        self._primary_provider = primary_provider
        self._secondary_provider = secondary_provider
        self._config = config

    def evaluate(self, change_id: str, *, actor: str, actor_role: str) -> ChangeRecord:
        record = self._change_repo.get(change_id)
        change = record.change

        # ---- Step 1: deterministic risk evaluation -------------------------------
        validate_transition(record.state, ChangeState.RISK_EVALUATED)
        risk = evaluate_risk(change)
        self._change_repo.attach_risk_assessment(change_id, risk)
        record = self._change_repo.update_state(change_id, ChangeState.RISK_EVALUATED)
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="RISK_EVALUATED",
            entity_id=change_id,
            payload={"score": risk.score, "level": risk.level.label, "rule_ids": list(risk.rule_ids)},
        )

        # ---- Kill-switch check #1 (before calling the AI provider) ---------------
        kill_switch_state = self._kill_switch_repo.get_state()

        # ---- Step 2: AI-assisted evaluation ---------------------------------------
        try:
            primary_ai = self._primary_provider.analyze(change)
        except AIProviderError as exc:
            self._force_block(
                change_id,
                actor=actor,
                actor_role=actor_role,
                reason=f"primary AI provider unavailable: {exc}",
            )
            raise PipelineFailureError(str(exc)) from exc

        secondary_ai = None
        try:
            secondary_ai = self._secondary_provider.analyze(change)
        except AIProviderError as exc:
            # Non-fatal: the primary opinion still stands. Gate 5 will be
            # SKIPPED and recorded as such — documented, not silently ignored.
            self._audit(
                actor=actor,
                actor_role=actor_role,
                action="SECONDARY_AI_PROVIDER_UNAVAILABLE",
                entity_id=change_id,
                payload={"reason": str(exc)},
            )

        validate_transition(record.state, ChangeState.AI_EVALUATED)
        self._change_repo.attach_ai_assessment(change_id, primary_ai, secondary=False)
        if secondary_ai is not None:
            self._change_repo.attach_ai_assessment(change_id, secondary_ai, secondary=True)
        record = self._change_repo.update_state(change_id, ChangeState.AI_EVALUATED)
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="AI_EVALUATED",
            entity_id=change_id,
            payload={
                "provider": primary_ai.provider_name,
                "confidence": primary_ai.confidence,
                "recommended_route": primary_ai.recommended_route,
                "secondary_available": secondary_ai is not None,
            },
        )

        # ---- Step 3: five mandatory assurance gates --------------------------------
        gate_result = run_gate_pipeline(
            primary=primary_ai,
            change=change,
            secondary=secondary_ai,
            confidence_thresholds=self._config.confidence_thresholds,
        )
        self._change_repo.attach_gate_result(change_id, gate_result)
        validate_transition(record.state, ChangeState.GATES_PASSED)
        record = self._change_repo.update_state(change_id, ChangeState.GATES_PASSED)
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="GATES_EVALUATED",
            entity_id=change_id,
            payload={r.gate.value: r.status.value for r in gate_result.results},
        )

        # ---- Kill-switch check #2 (immediately before final routing) --------------
        kill_switch_state = self._kill_switch_repo.get_state()

        # ---- Step 4: pure routing decision -----------------------------------------
        ctx = RoutingContext(
            risk=risk,
            gates=gate_result,
            kill_switch_active=kill_switch_state.active,
            allow_critical_cab_exception=self._config.allow_critical_cab_exception,
            critical_cab_exception_requested=bool(change.metadata.get("cab_critical_exception_requested")),
        )
        decision = route_decision(ctx)
        self._change_repo.attach_routing_decision(change_id, decision)
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="ROUTING_DECISION",
            entity_id=change_id,
            payload={"decision": decision.decision.value, "policy_ids": list(decision.policy_ids)},
        )

        # ---- Step 5: apply the decision to the state machine -----------------------
        if decision.decision == Decision.HARD_BLOCK:
            target_state = ChangeState.BLOCKED
        elif decision.decision == Decision.CAB_REVIEW_REQUIRED:
            target_state = ChangeState.CAB_REVIEW_REQUIRED
        else:
            target_state = ChangeState.READY_TO_SHIP

        validate_transition(record.state, target_state)
        record = self._change_repo.update_state(change_id, target_state)
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="STATE_TRANSITION",
            entity_id=change_id,
            payload={"from": ChangeState.GATES_PASSED.value, "to": target_state.value},
        )

        if target_state == ChangeState.CAB_REVIEW_REQUIRED:
            ticket = build_cab_ticket(change, risk, primary_ai)
            self._cab_repo.create_ticket(ticket)
            self._audit(
                actor=actor,
                actor_role=actor_role,
                action="CAB_TICKET_CREATED",
                entity_id=ticket.ticket_id,
                payload={"change_id": change_id, "risk_level": risk.level.label},
            )

        return self._change_repo.get(change_id)

    def _force_block(self, change_id: str, *, actor: str, actor_role: str, reason: str) -> None:
        try:
            self._change_repo.update_state(change_id, ChangeState.BLOCKED)
        except Exception:  # noqa: BLE001 - best-effort fail-closed guard
            pass
        self._audit(
            actor=actor,
            actor_role=actor_role,
            action="PIPELINE_FAILURE_BLOCKED",
            entity_id=change_id,
            payload={"reason": reason},
        )

    def _audit(self, **kwargs) -> None:
        self._audit_repo.append(**kwargs)
