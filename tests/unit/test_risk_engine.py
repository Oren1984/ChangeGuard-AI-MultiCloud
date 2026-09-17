from __future__ import annotations

from src.domain.enums.risk_level import RiskLevel
from src.domain.risk.engine import evaluate_risk


def test_low_risk_app_change_scores_low(low_risk_app_change):
    result = evaluate_risk(low_risk_app_change)
    assert result.level == RiskLevel.LOW
    assert result.triggered_rules == ()


def test_public_network_exposure_is_critical(public_exposure_terraform_change):
    result = evaluate_risk(public_exposure_terraform_change)
    assert result.level == RiskLevel.CRITICAL
    assert result.has_mandatory_violation
    assert "RISK-NET-001" in result.rule_ids


def test_destructive_migration_without_rollback_is_critical(destructive_migration_change):
    result = evaluate_risk(destructive_migration_change)
    assert result.level == RiskLevel.CRITICAL
    assert "RISK-DB-001" in result.rule_ids
    assert "RISK-DB-003" in result.rule_ids


def test_iam_wildcard_is_critical(iam_wildcard_change):
    result = evaluate_risk(iam_wildcard_change)
    assert result.level == RiskLevel.CRITICAL
    assert "RISK-IAM-001" in result.rule_ids


def test_blast_radius_reflects_dependency_count(low_risk_app_change):
    import dataclasses

    changed = dataclasses.replace(
        low_risk_app_change, service_dependencies=("svc-a", "svc-b", "svc-c", "svc-d")
    )
    result = evaluate_risk(changed)
    assert result.blast_radius == 4
    assert any(r.rule_id == "RISK-BLAST-001" for r in result.triggered_rules)
