# ChangeGuard AI MultiCloud — Autonomous Change Risk & Release Governance POC

A change-governance platform that lets AI *advise* on release risk while a deterministic engine, five mandatory assurance gates, and human approval decide what actually ships.

---

## The Why

Most production outages trace back to a change: a Terraform plan that opens a security group to the world, a migration that drops a column nobody backed up, an IAM policy with a stray wildcard. Enterprises try to catch these with CAB (Change Advisory Board) review, but manual review doesn't scale and automated pipelines don't reliably encode "is this actually safe."

Generative AI can summarize a diff, spot a suspicious pattern, and draft a CAB brief faster than any human. But an LLM is also a fluent liar: it can hallucinate evidence, misjudge severity, or — if wired in carelessly — recommend disabling the very controls meant to stop it. **AI is not trustworthy enough to be the approver of production changes.** It is trustworthy enough to be a fast, tireless first-pass reviewer, if — and only if — its output is boxed in by deterministic rules, validated before it's trusted, and never allowed the last word.

That's the thesis this POC demonstrates: deterministic controls decide, humans approve, AI assists, and every decision is explainable and auditable after the fact.

## The What

ChangeGuard AI MultiCloud is a shift-left release-governance platform. It ingests a normalized change (application code, Terraform, Helm/K8s config, DB migration, IAM policy, API contract, or general config), runs it through a **deterministic risk engine**, generates a **controlled AI-assisted impact summary**, validates that summary through **five mandatory assurance gates**, and routes the change to exactly one outcome:

| Decision | Meaning |
|---|---|
| `AUTO_CLEAR` | Low/medium risk, all gates passed, evidence complete — proceeds automatically. |
| `CAB_REVIEW_REQUIRED` | High risk, a gate warning, or an AI inconsistency — a human (never the submitter) must approve or reject. |
| `HARD_BLOCK` | Critical/mandatory rule violation or a failed assurance gate — blocked outright, AI cannot override this. |

A Change Advisory Board (CAB) workflow handles the middle path, with separation-of-duties enforced (submitters cannot approve their own changes). Every step — risk evaluation, AI opinion, gate result, routing decision, CAB decision, kill-switch change — is written to a SHA-256 hash-chained, tamper-evident audit log. The system is provider-independent (any VCS, any cloud, any LLM behind a `Protocol`) and ships with reference Terraform for both AWS and GCP, validated but never deployed by this repository.

This is **not** a chatbot and **not** an autonomous deployment system. It never merges code, never calls a cloud API, and never executes a command suggested by a model.

## The How

- **Modular monolith, Clean Architecture.** `domain/` (pure, no framework imports) → `application/` (use cases, orchestration, gates, routing) → `adapters/`+`ports/` (SQLAlchemy, AI providers, VCS adapters via `typing.Protocol`) → `api/` (FastAPI).
- **Deterministic risk engine.** ~16 rules over the normalized change (network exposure, destructive Terraform, IAM wildcards, destructive migrations, missing rollback/maintenance window, blast radius, test status, breaking API changes, ...) produce a score, a `LOW/MEDIUM/HIGH/CRITICAL` level, and the evidence behind it. No AI involved.
- **AI provider protocol.** A deterministic, offline `MockAIProvider` is the default and is all tests run against; an `ExternalAIProvider` adapter exists but is disabled unless explicitly configured — no network access or API key is ever required to run this project.
- **Five mandatory assurance gates**, run on every AI response: schema validation, grounding (no fabricated evidence), confidence thresholds, categorical safety blocklist, and cross-opinion consistency.
- **Pure decision router.** A single function turns risk + gate results + kill-switch state into one of the three decisions. It never even receives the AI's own recommendation as an input — structurally, AI cannot override a hard block.
- **PostgreSQL-only, hash-chained audit trail.** Every audit record links to the previous one's hash; tampering with history is detectable (not preventable — see limitations below).
- **Docker Compose environment**: app + PostgreSQL 16 + Alembic migrations + optional Prometheus, one command to stand up.
- **Layered Pytest suite**: unit (pure, no I/O), PostgreSQL integration, AI assurance, API/security, and end-to-end — 78 tests, all passing, no SQLite anywhere.
- **AWS and GCP Terraform references**: ECS Fargate/RDS/Secrets Manager vs. Cloud Run/Cloud SQL/Secret Manager, both `fmt`+`validate` clean, neither ever applied.

### Architecture flow

```mermaid
flowchart LR
    A[Webhook / direct submit] --> B[Normalize to ChangeRequest]
    B --> C[Deterministic Risk Engine]
    C --> D[AI Provider: primary + secondary opinion]
    D --> E[5 Assurance Gates]
    E --> F[Pure Decision Router]
    F -->|AUTO_CLEAR| G[READY_TO_SHIP]
    F -->|CAB_REVIEW_REQUIRED| H[CAB Ticket]
    H -->|approve| G
    H -->|reject| I[BLOCKED]
    F -->|HARD_BLOCK| I
    C -.audit.-> J[(Hash-chained Audit Log)]
    D -.audit.-> J
    E -.audit.-> J
    F -.audit.-> J
    H -.audit.-> J
```

## Key capabilities

- Deterministic, explainable risk scoring — independent of any AI call.
- AI advisory output that is schema-validated, grounding-checked, confidence-gated, safety-screened, and cross-checked for consistency before it can influence anything.
- A kill switch, checked twice per evaluation, that guarantees no AI-assisted change auto-clears while active.
- Separation-of-duties CAB workflow with a real, audited approve/reject decision trail.
- Tamper-evident audit chain with a `/api/v1/audit/verify` endpoint and integration tests that prove tampering and record deletion are both detected.
- A read-only dashboard for system status, risk distribution, CAB queue, and recent decisions.

## Quick start

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose ps
```

Then:

- API docs: http://localhost:8000/docs

- Dashboard: http://localhost:8000/dashboard

- Health / readiness / metrics: `/health`, `/ready`, `/metrics`

Tear down: `docker compose down` (add `-v` to also drop the database volume).

## Demo commands

Fifteen reproducible scenarios (low-risk auto-clear, public network exposure, IAM wildcard, destructive migration, fabricated AI evidence, low-confidence AI, dangerous AI recommendation, inconsistent AI opinions, active kill switch, duplicate webhook, self-approval attempt, tampered audit chain, ...) live in `demo/fixtures/` and run against a live instance:

```bash
docker compose exec app python demo/scripts/run_demo.py
```

## API endpoints

```
POST   /api/v1/changes                       submit a normalized change
GET    /api/v1/changes                       list changes (paginated, filterable by state)
GET    /api/v1/changes/{id}                   get a change's full evaluation record
POST   /api/v1/changes/{id}/evaluate          run risk → AI → gates → routing
GET    /api/v1/changes/{id}/cab-brief         executive CAB brief for a change
POST   /api/v1/changes/{id}/cab/approve       CAB approval (separation of duties enforced)
POST   /api/v1/changes/{id}/cab/reject
POST   /api/v1/webhooks/{provider}            simulated GitHub/GitLab intake (idempotent)
GET    /api/v1/audit/verify                   hash-chain verification
GET    /api/v1/system/status                  aggregate system/dashboard status
POST   /api/v1/admin/kill-switch/activate     admin-only
POST   /api/v1/admin/kill-switch/deactivate   admin-only
GET    /health   /ready   /metrics
```

Actor identity for this POC is via `X-ChangeGuard-Actor` / `X-ChangeGuard-Role` headers — a documented, explicit boundary, not production-grade authentication (see [Security and governance boundaries](#security-and-governance-boundaries)).

## Testing

```bash
# Unit (no DB, no network)
pytest tests/unit -v

# Everything else (needs PostgreSQL — see docker-compose.yml's `db` service)
CHANGEGUARD_DATABASE_URL=postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard \
  pytest tests/integration tests/assurance tests/security tests/e2e -v
```

| Layer | What it covers | Count |
|---|---|---|
| `tests/unit` | Risk rules, state machine, gates, pure router | 22 |
| `tests/integration` | Real PostgreSQL: repositories, JSONB, cascades, hash-chain tamper/sequence detection, migrations | 24 |
| `tests/assurance` | Full pipeline against every AI-assurance scenario (fabrication, low confidence, unsafe recommendation, inconsistency, provider outage, kill switch mid-flight) | 11 |
| `tests/security` | Actor/role validation, self-approval prevention, oversized payloads, injection-as-inert-data, error redaction, idempotency, invalid transitions | 13 |
| `tests/e2e` | Full webhook → evaluation → CAB → audit → dashboard flow | 8 |

All 78 tests pass. SQLite is never used anywhere in the codebase or test suite.

## Repository structure

```
src/
├── domain/          entities, enums, risk engine, state machine, policies — no framework imports
├── application/     use cases, orchestration pipeline, 5 gates, pure router
├── ports/            Protocol definitions for AI/VCS/repository providers
├── adapters/        SQLAlchemy, mock/external AI, GitHub/GitLab normalizers, webhook dispatch
├── api/             FastAPI routes, schemas, dependency wiring
├── observability/   structured logging, correlation IDs, Prometheus metrics
├── security/        redaction, actor/role header parsing
└── main.py
tests/{unit,integration,assurance,security,e2e}/
demo/{fixtures,scripts}/
migrations/          Alembic
infrastructure/{aws,gcp}/   Terraform reference architectures (validated, never applied)
docs/                architecture, risk model, AI governance, CAB workflow, security, ops, roadmap
```

## Security and governance boundaries

- **Identity is header-based** (`X-ChangeGuard-Actor`/`X-ChangeGuard-Role`) — a documented POC boundary. Production needs OIDC/OAuth2, an enterprise IdP, signed tokens, and mTLS (see roadmap doc).
- **The audit chain is tamper-evident, not immutable.** SHA-256 hash chaining detects retroactive mutation or record deletion; it does not physically prevent someone with direct database access from rewriting the whole chain consistently. External WORM storage/ledger anchoring is a documented production-hardening step.
- **AI never gets the last word.** The pure decision router's function signature doesn't even accept the AI's recommended route as an argument — this is enforced by the type system, not just policy.
- No direct cloud SDK calls from domain/application code; no shell execution from model output; no `eval`; parameterized queries throughout; secrets redacted from logs and error responses; non-root Docker user.

## POC limitations

- Synchronous, single-process evaluation pipeline — no background workers/queue.
- Header-based actor identity, not a real auth system.
- In-database hash chain rather than external ledger anchoring.
- Terraform is validated (`fmt`+`validate`) but never applied — no cloud resources exist because of this repository.
- The dashboard is read-only; CAB decisions are API-driven by design.

## Production-hardening roadmap

OIDC/OAuth2 + enterprise IdP + mTLS · async worker/queue for evaluation · WORM/ledger audit anchoring · multi-AZ RDS/Cloud SQL · private networking end-to-end · disaster recovery runbooks. Full detail in [`docs/TRADEOFFS_AND_PRODUCTION_ROADMAP.md`](docs/TRADEOFFS_AND_PRODUCTION_ROADMAP.md).

## Enterprise AI Governance Trilogy

ChangeGuard is the **pre-deployment** member of a three-part governance architecture:

- **ChangeGuard AI** (this repo) — is a proposed change safe enough to progress toward deployment?
- **ArchGuard AI** — runtime incident response and operational resilience once something is already live.
- **PolicyGuard AI** (future) — continuous post-deployment policy, drift, and compliance governance.

All three share the same philosophy — deterministic gates, fail-closed behavior, human-in-the-loop, provider-independence, tamper-evident auditability — but own distinct business questions and never overlap in responsibility. See [`docs/TRILOGY_POSITIONING.md`](docs/TRILOGY_POSITIONING.md).
