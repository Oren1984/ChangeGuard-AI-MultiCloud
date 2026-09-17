from __future__ import annotations

from src.application.orchestration.evaluation_pipeline import EvaluationPipeline
from src.domain.entities.change_record import ChangeRecord


class EvaluateChangeUseCase:
    def __init__(self, pipeline: EvaluationPipeline) -> None:
        self._pipeline = pipeline

    def execute(self, change_id: str, *, actor: str, actor_role: str) -> ChangeRecord:
        return self._pipeline.evaluate(change_id, actor=actor, actor_role=actor_role)
