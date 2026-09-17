# Change Risk Model

The deterministic risk engine (`src/domain/risk/`) is pure Python: no AI, no I/O, no
network. Given a `ChangeRequest`, `evaluate_risk()` always returns the same
`RiskAssessment` for the same input. This is what the routing decision is actually
anchored to — the AI's opinion (see `docs/AI_ASSURANCE_AND_GOVERNANCE.md`) is advisory
context layered on top, never a substitute.

## Inputs

Everything the engine reasons over comes from the normalized `ChangeRequest`: change
type, changed files, diff text, Terraform plan evidence (resource addresses, types,
actions, attributes), migration statements, rollback-plan flag, maintenance window,
service dependencies, environment target, and test-pass status. No field is inferred
from an external system at evaluation time — if it isn't on the `ChangeRequest`, the
engine cannot see it.

## Rule catalog

Rules are plain functions (`ChangeRequest -> TriggeredRule | None`), registered in
`RULE_REGISTRY`. Each has a stable `rule_id`, a `severity` (0-100), a human-readable
`description`, `evidence`, and a `required_action`.

| Rule ID | Category | Severity | Trigger |
|---|---|---|---|
| RISK-NET-001 | network_exposure | 75 / **95** (prod) | Terraform plan opens `0.0.0.0/0` or `::/0` |
| RISK-TF-001 | destructive_infrastructure | 65 / **90** (prod) | Terraform plan deletes a resource (no matching create) |
| RISK-TF-002 | resource_replacement | 55 | Terraform plan replaces (delete+create) a resource |
| RISK-IAM-001 | iam_wildcard | **95** | IAM policy change contains a wildcard `*` action/resource |
| RISK-SEC-001 | security_control_removal | **85** | A security group/IAM policy/firewall resource is deleted |
| RISK-DB-001 | destructive_migration | 70 / **90** (prod) | Migration contains `DROP`/`TRUNCATE` |
| RISK-DB-002 | irreversible_migration | 75 | `ALTER TABLE ... DROP COLUMN` |
| RISK-DB-003 | rollback_missing | 60 | Production DB migration without a rollback plan |
| RISK-OPS-001 | rollback_missing | 50 | High-impact prod change (migration/terraform/IAM) with no rollback plan |
| RISK-OPS-002 | maintenance_window_missing | 40 | High-impact prod change with no maintenance window |
| RISK-API-001 | api_breaking_change | 55 | API contract change flagged breaking (metadata or diff marker) |
| RISK-BLAST-001 | blast_radius | 30-70 | 3+ declared dependent services |
| RISK-QA-001 | test_failure | 50 | `tests_passed=false` |
| RISK-QA-002 | test_missing | 30 | `tests_passed` unknown |
| RISK-SIZE-001 | change_size | 25 | More than 40 changed files |
| RISK-ENV-001 | production_target | 10 | `environment_target=production` |
| RISK-CFG-001 | sensitive_configuration | 45 | Configuration change touches secret/token/credential-looking keys |

**Mandatory rules** (severity ≥ 90) force `RiskLevel.CRITICAL` regardless of the numeric
score, and the router treats any mandatory violation as an automatic `HARD_BLOCK`
candidate (see `docs/AI_ASSURANCE_AND_GOVERNANCE.md`'s routing table). Every rule is
independently unit-tested in `tests/unit/test_risk_engine.py`.

## Score calculation and thresholds

```
score = min(100, sum(severity for every triggered rule))
has_mandatory_violation = any(rule.severity >= 90 for rule in triggered)

level = CRITICAL if has_mandatory_violation
        else CRITICAL if score >= 80
        else HIGH     if score >= 50
        else MEDIUM   if score >= 25
        else LOW
```

Deliberately additive and uncapped-per-rule-but-capped-in-total: a handful of small
findings compounds into a higher tier exactly the way a human reviewer's gut sense
would, without needing a bespoke weighting DSL.

## Blast-radius logic

`blast_radius = len(change.service_dependencies)`. Zero dependencies is described as
"limited to this component"; 1-2 as "limited blast radius"; 3+ as "wide blast radius" —
and 3+ also triggers RISK-BLAST-001, scaling its severity with the dependency count
(`min(30 + 5*count, 70)`).

## Worked examples

- **Low-risk app change**: `application_code`, staging, tests passed, rollback plan
  present, no dependencies → no rules trigger → score 0 → `LOW` → eligible for
  `AUTO_CLEAR`.
- **Public security-group exposure in production**: RISK-NET-001 fires at severity 95
  (prod) → `has_mandatory_violation=True` → `CRITICAL` regardless of anything else →
  router forces `HARD_BLOCK`.
- **Breaking API change to production with a maintenance window and rollback plan**:
  RISK-API-001 (55) + RISK-ENV-001 (10) = 65 → `HIGH` → router requires
  `CAB_REVIEW_REQUIRED` (not a hard block — no mandatory rule fired).

## Deterministic vs. AI responsibility

| | Deterministic risk engine | AI provider |
|---|---|---|
| Runs without network/API keys | Always | Always (Mock is offline by default) |
| Can force `HARD_BLOCK` | Yes, via mandatory rules | **Never** — the router doesn't even accept the AI's recommendation as an argument |
| Basis for routing decision | Authoritative | Advisory only (surfaced in the CAB brief/dashboard) |
| Testable in isolation | Yes — pure function, zero I/O | Yes — deterministic Mock provider, but its opinion is never load-bearing for the decision |
