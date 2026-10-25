# Governance and Validation

This document covers who decides what, which controls are implemented, how the system was validated, and what is still missing. "Implemented" means it is in the code and covered by tests or the demo. Anything else is marked as a gap.

## Human oversight

- **AI is advisory.** The AI assessment is stored and shown in the CAB brief, but `route_decision()` has no parameter for the AI's recommended route. AI output can only affect the outcome by *failing* or *warning* on an assurance gate, and both push toward more human review, never less.
- **CAB review** is required for HIGH risk, any gate warning, missing operational evidence (rollback plan or maintenance window), or an active kill switch. A CAB ticket records the risk level, triggered rules and their descriptions, whether a rollback plan and maintenance window exist, dependent services, suggested reviewer roles, and the AI's executive brief.
- **Separation of duties.** The submitter of record is always the `X-ChangeGuard-Actor` of the submit request; a `submitted_by` value in the body is overwritten. That actor cannot approve or reject the change (HTTP 403), whatever role header they send.
- **Kill switch.** An admin can turn off AI-assisted auto-clear at any time. While it is active, every change that would have auto-cleared goes to CAB review instead. The router reads its state immediately before routing.
- **No autonomous action.** `READY_TO_SHIP` is the last state. The system does not merge, deploy, run commands, or call cloud APIs, and it never runs text suggested by a model.

## Authority boundaries

| Actor | Can | Cannot |
| --- | --- | --- |
| AI provider (mock or external) | Write a summary, impact map, reviewer suggestions, and a suggested route and risk level | Choose the route, override a block, or change state |
| Deterministic risk engine | Score the change and flag mandatory violations | Be overridden by AI |
| Decision router | Choose exactly one of `AUTO_CLEAR`, `CAB_REVIEW_REQUIRED`, `HARD_BLOCK` | Unblock a CRITICAL change unless the CAB exception is both enabled in config **and** requested on the change |
| `developer` / `operator` | Submit and evaluate changes | Record CAB decisions or change the kill switch |
| `approver` / `security_reviewer` / `admin` | Approve or reject CAB tickets for changes they did not submit | Decide their own changes |
| `admin` | Turn the kill switch on or off (audited) | Bypass the state machine |
| Anyone | Read changes, CAB briefs, system status, the dashboard, and audit verification | — (these read endpoints need no identity headers; see gaps) |

Every state change is checked against the allow-list in `src/domain/state_machine/transitions.py`. `READY_TO_SHIP`, `BLOCKED`, and `CANCELLED` are terminal. Any other transition returns HTTP 409.

## Security and privacy controls

**Implemented**

- Strict input schemas: unknown fields are rejected (`extra="forbid"`), and there are length and count limits on IDs, diffs (500,000 characters), files, migration statements, and dependencies.
- Request size limit (`CHANGEGUARD_MAX_PAYLOAD_BYTES`, HTTP 413).
- Actor ID charset and length validation, and a fixed role enum (HTTP 401 if invalid or missing on write endpoints).
- Five assurance gates, including a safety blocklist (`terraform destroy`, `disable audit`, `bypass approval`, `rm -rf`, and others) and a grounding check that rejects evidence not present in the submitted change.
- SQLAlchemy ORM with bound parameters. No `eval`, and no shell execution of model output. Injection-style strings are stored as inert data, and a security test covers this.
- Error responses: mapped exceptions are returned with Bearer tokens and AWS access-key patterns redacted. Unexpected errors return a generic 500 with no stack trace. The log formatter applies the same redaction.
- Response headers `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and a correlation ID on every response.
- SHA-256 hash-chained audit log covering risk evaluation, AI evaluation, gates, routing, state changes, CAB decisions, kill-switch changes, and pipeline failures.
- Container runs as a non-root user. Configuration and secrets come from environment variables. `.env` and `certs/*` are git-ignored.
- Reference Terraform keeps databases private (RDS `publicly_accessible = false`, Cloud SQL private IP only), exposes the AWS ALB on 443 only, and stores DB credentials in a secret manager.

**Privacy:** the service stores what is submitted: repository names, branches, file paths, diffs, migration statements, and actor IDs. It does not collect other personal data. All demo and test data is synthetic. Diffs are stored as submitted and are not scrubbed. Rule `RISK-CFG-001` only *flags* configuration changes that mention secret-like keys.

## Validation approach

| Layer | Location | Tests | What it covers |
| --- | --- | --- | --- |
| Unit | `tests/unit` | 22 | Risk rules, state machine, gates with the mock provider, pure router |
| Integration | `tests/integration` | 24 | Real PostgreSQL repositories, JSONB, cascades, migrations, detection of hash-chain tampering and sequence gaps |
| Assurance | `tests/assurance` | 10 | Full pipeline against fabricated evidence, low confidence, unsafe advice, inconsistency, provider outage, kill switch (in-memory fakes) |
| Security | `tests/security` | 13 | Actor/role validation, self-approval, oversized payloads, injection as inert data, error redaction, idempotency, invalid transitions |
| End-to-end | `tests/e2e` | 9 | Webhook → evaluation → CAB → audit → dashboard through the API with PostgreSQL |

Commands (from the repo root, with PostgreSQL running and `CHANGEGUARD_DATABASE_URL` set):

```bash
ruff check src tests
pytest tests/unit -v
alembic upgrade head
pytest tests/integration tests/assurance tests/security tests/e2e -v
pytest tests --cov=src --cov-report=term-missing
```

`tests/integration` truncates all application tables before each test. Don't point it at a database whose data you want to keep.

### Execution status

| Check | Status |
| --- | --- |
| `ruff check src tests` | **Passed** locally (2026-10-25) |
| Unit tests | **22 passed** locally |
| Integration + assurance + security + e2e | **56 passed** locally against PostgreSQL 16 (1 third-party deprecation warning) |
| Full run with coverage | **78 passed**, **91%** line coverage of `src/` |
| Alembic `upgrade head` on an empty database | **Passed** locally |
| Demo script (15 scenarios) | **All outcomes matched expectations** locally (see [DEMO_AND_OPERATIONS.md](DEMO_AND_OPERATIONS.md)) |
| `docker compose config` | **Valid** locally |
| `terraform fmt -check` (AWS, GCP) | **Passed** locally |
| `terraform validate` | **Not verified locally.** The provider plugin failed to start in this environment. It passed in GitHub Actions |
| `docker build` | **Not verified locally.** It failed on TLS inspection during `pip install` in this environment. It passed in GitHub Actions |
| GitHub Actions CI (`.github/workflows/ci.yml`) | Last run on commit `87c677a` (the current application code): **test, docker-build, terraform (aws), terraform (gcp) all succeeded** |

The local run used the app under Uvicorn on the host against a disposable `postgres:16` container, not the full Compose stack. Port conflicts and the TLS-inspection build failure prevented a full Compose run here.

## Known limitations

- **No real authentication.** Identity is two trusted headers, so any client can claim any role. Read endpoints (`GET /api/v1/changes…`, `/cab-brief`, `/audit/verify`, `/system/status`, `/dashboard`, `/metrics`) need no headers at all.
- **Webhook intake is simulated.** There is no HMAC signature check and no call back to GitHub or GitLab. Intake creates a `PROPOSED` change but doesn't evaluate it.
- **AI is mocked.** The mock reasons only over submitted fields, and failure modes are triggered by `metadata._demo`. The external adapter is unverified, and the Gate 5 second opinion is always the mock in drift mode.
- **The audit chain shows tampering but does not prevent it.** Someone with database write access can rewrite the whole chain consistently. There is no external anchoring.
- **Audit payloads are not redacted.** `redact_mapping()` exists in `src/security/redaction.py` but is not applied to audit or stored change data.
- **Metrics are mostly unwired.** Only `changeguard_http_errors_total` is incremented. Decision, risk-level, gate-failure, and duration metrics stay at zero.
- `cors_allow_origins` is defined in settings but not applied to the app.
- Evaluation is synchronous in the request, with one process and no queue.
- Policy changes require code changes. Rules are Python functions with fixed severities.
- The Compose file publishes PostgreSQL on host port 5432 with placeholder credentials. This is fine for a workstation and nowhere else.
- Terraform has never been applied. Settings such as single-AZ RDS, `deletion_protection = false` on Cloud SQL, and an optional public Cloud Run invoker are POC choices.

## Focused future improvements

1. Replace header identity with OIDC/OAuth2 tokens and require authentication on read endpoints.
2. Verify webhook signatures (GitHub `X-Hub-Signature-256`, GitLab token) and optionally trigger evaluation on intake.
3. Apply `redact_mapping()` to audit payloads and stored diffs.
4. Wire the existing Prometheus metrics into the evaluation pipeline.
5. Anchor audit-chain checkpoints in external write-once storage.
6. Validate the external AI adapter against a real provider behind the same five gates, with timeouts and retries.
7. Move evaluation to a background worker if a real AI provider makes requests slow.
