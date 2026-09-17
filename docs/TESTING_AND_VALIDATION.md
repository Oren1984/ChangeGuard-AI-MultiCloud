# Testing and Validation

## Test layers

| Layer | Directory | Dependencies | Purpose |
|---|---|---|---|
| Unit | `tests/unit` | None (no DB, no network) | Risk rules, risk scoring, state machine, pure router, gates, mock provider |
| Integration | `tests/integration` | Real PostgreSQL 16 | Repository CRUD, JSONB round-trips, cascades, hash-chain tamper/sequence-gap detection, Alembic schema validity |
| Assurance | `tests/assurance` | None (fake repositories) | Full `EvaluationPipeline` run against every AI-assurance scenario |
| Security | `tests/security` | None (FastAPI `TestClient` + fake repositories via `dependency_overrides`) | Actor/role validation, separation of duties, payload limits, injection-as-inert-data, error redaction, idempotency, invalid transitions |
| E2E | `tests/e2e` | None (same `TestClient` harness as security) | Full webhook → evaluate → CAB → audit → dashboard flow over real HTTP calls |

## Test environment

Unit, assurance, security, and e2e tests need **no external services** — they run
against pure functions or in-memory fakes
(`tests/fixtures/fake_repositories.py`) that implement the exact same `Protocol`s the
real SQLAlchemy repositories do. Only the integration layer needs PostgreSQL.

## PostgreSQL-only policy

SQLite is never used, anywhere, in application code, test fixtures, or CI
configuration. `docker-compose.yml` provisions PostgreSQL 16; the integration test
`conftest.py` connects to it directly.

## Test commands

```bash
# No DB required:
pytest tests/unit tests/assurance tests/security tests/e2e -v

# Needs PostgreSQL (e.g. `docker compose up -d db` first):
CHANGEGUARD_DATABASE_URL=postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard \
  alembic upgrade head
CHANGEGUARD_DATABASE_URL=postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard \
  pytest tests/integration -v

# Everything:
pytest tests -v
```

## Scenario matrix (demo fixtures ↔ test coverage)

| Demo scenario (`demo/fixtures/`) | Exercised by |
|---|---|
| 01 Low-risk auto-clear | `tests/e2e::test_webhook_intake_through_auto_clear`, `tests/assurance::test_happy_path_auto_clears` |
| 02 Medium risk / confidence warning | `tests/assurance::test_warning_confidence_requires_cab_review` |
| 03 Public network exposure | `tests/unit::test_public_network_exposure_is_critical` |
| 04 Delete critical resource | Risk rule unit-tested directly (`RISK-TF-001`); scenario run confirms end-to-end |
| 05 IAM wildcard | `tests/unit::test_iam_wildcard_is_critical` |
| 06 Destructive SQL migration | `tests/unit::test_destructive_migration_without_rollback_is_critical` |
| 07 High risk requires CAB | `tests/e2e::test_full_cab_flow_to_ready_to_ship` |
| 08 AI fabricated evidence | `tests/assurance::test_fabricated_evidence_hard_blocks`, `tests/unit::test_fabricated_evidence_fails_grounding_gate` |
| 09 AI low confidence | `tests/assurance::test_low_confidence_hard_blocks`, `tests/unit::test_low_confidence_fails_confidence_gate` |
| 10 AI dangerous recommendation | `tests/assurance::test_dangerous_recommendation_hard_blocks`, `tests/unit::test_dangerous_recommendation_fails_safety_gate` |
| 11 Inconsistent AI opinions | `tests/assurance::test_inconsistent_ai_opinions_require_cab_review` |
| 12 Active kill switch | `tests/assurance::test_kill_switch_activated_between_stages_blocks_auto_clear` |
| 13 Duplicate webhook | `tests/e2e::test_webhook_replay_is_idempotent`, `tests/security::test_duplicate_submission_is_idempotent` |
| 14 Self-approval attempt | `tests/security::test_self_approval_is_rejected` (+ spoofed-author variant) |
| 15 Tampered audit chain | `tests/integration::test_tampering_with_a_historical_record_is_detected`, `test_deleting_a_record_creates_a_sequence_discontinuity` |

All 15 demo scenarios were additionally run against the real, containerized stack
(`docker compose up -d` + `docker compose exec app python demo/scripts/run_demo.py`)
and produced the expected state/decision for every scenario.

## Expected evidence

- Unit: 22 tests, all passing, 0 skipped.
- Integration: 24 tests, all passing against a real PostgreSQL 16 container — includes
  direct proof that mutating a historical audit row is detected
  (`is_valid=False`, exact sequence identified) and that deleting a row creates a
  detectable sequence discontinuity.
- Assurance: 11 tests, all passing.
- Security: 13 tests, all passing.
- E2E: 8 tests, all passing.
- **Total: 78/78 passing.**

## Known blockers

None outstanding in the delivered codebase. One environment-specific note for
reproduction on this development machine: this Windows host runs an
Application-Control policy that blocks `psycopg`'s native DLL from loading directly in
the Windows Python venv, and a corporate antivirus TLS-inspection proxy that requires
trusting its root CA before any tool can reach the public internet from inside a
Docker container. Neither affects the actual codebase or a normal CI/Linux
environment: all PostgreSQL-dependent tests were run and verified inside Linux
containers (see `docker-compose.yml` / `.github/workflows/ci.yml`, and the container
image itself trusts an optional local CA via `certs/` if one is present — a no-op on
an unrestricted network).
