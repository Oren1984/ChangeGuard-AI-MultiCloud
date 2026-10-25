# Demo and Operations

This guide covers how to run ChangeGuard AI MultiCloud on a workstation, run the demo, and fix common problems. It runs entirely offline: there is no cloud account, API key, or LLM to set up.

## Prerequisites

| For | You need |
| --- | --- |
| Docker startup (recommended) | Docker Engine or Docker Desktop with Compose v2 (`docker compose`) |
| Local (non-Docker) startup and tests | Python **3.12** (`pyproject.toml` requires `>=3.12,<3.13`) and PostgreSQL 16 (the Compose `db` service works) |
| Optional | Terraform ≥ 1.9 if you want to run `fmt`/`validate` on the reference infrastructure |

Free ports used by default: **8000** (app), **5432** (PostgreSQL), and **9090** (Prometheus, only with the `monitoring` profile).

## Configuration

Settings are read from environment variables with the `CHANGEGUARD_` prefix, or from a `.env` file (`src/config.py`). Start from the template:

```bash
cp .env.example .env
```

| Variable | Default | Meaning |
| --- | --- | --- |
| `CHANGEGUARD_DATABASE_URL` | `postgresql+psycopg://…@db:5432/changeguard` in `.env.example` | PostgreSQL connection. Use host `db` inside Compose and `localhost` when running on the host |
| `CHANGEGUARD_AI_PROVIDER` | `mock` | `mock` (offline, deterministic) or `external` |
| `CHANGEGUARD_AI_EXTERNAL_BASE_URL` / `_API_KEY` | empty | Used only when the provider is `external`. Leave empty for the demo |
| `CHANGEGUARD_CONFIDENCE_APPROVAL_THRESHOLD` | `0.70` | Below this, Gate 3 warns (forces CAB review) |
| `CHANGEGUARD_CONFIDENCE_HARD_FLOOR` | `0.35` | Below this, Gate 3 fails (hard block) |
| `CHANGEGUARD_ALLOW_CRITICAL_CAB_EXCEPTION` | `false` | If `true`, a CRITICAL change that also sets `metadata.cab_critical_exception_requested` goes to CAB instead of being blocked |
| `CHANGEGUARD_KILL_SWITCH_DEFAULT_ACTIVE` | `false` | Kill-switch state seeded on first startup |
| `CHANGEGUARD_MAX_PAYLOAD_BYTES` | `1000000` | Larger requests get HTTP 413 |
| `CHANGEGUARD_ENVIRONMENT`, `CHANGEGUARD_LOG_LEVEL` | `local`, `INFO` | Labels and log verbosity |
| `POSTGRES_USER` / `_PASSWORD` / `_DB` | `changeguard` | Local placeholder credentials used by Compose only |

`.env` is git-ignored. The values in `.env.example` are local placeholders, not real secrets.

## Startup option 1: Docker Compose

```bash
cp .env.example .env
docker compose build
docker compose up -d
docker compose ps
```

Startup order is enforced by Compose: `db` becomes healthy, then `migrate` runs `alembic upgrade head` and exits, then `app` starts on port 8000.

- API docs (Swagger UI): http://localhost:8000/docs
- Dashboard: http://localhost:8000/dashboard
- Health / readiness / metrics: `/health`, `/ready`, `/metrics`
- Optional Prometheus: `docker compose --profile monitoring up -d`, then http://localhost:9090

Stop with `docker compose down`. Add `-v` to also delete the database volume, which resets all demo data.

## Startup option 2: local Python process

Useful for development and required for running the test suite, because the runtime image does not include `tests/`.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

docker compose up -d db                # or any PostgreSQL 16 instance
export CHANGEGUARD_DATABASE_URL=postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard
alembic upgrade head
uvicorn src.main:app --host 127.0.0.1 --port 8000
```

Environment variables take precedence over `.env`. Set `CHANGEGUARD_DATABASE_URL` explicitly, because the `.env.example` value points to the Compose hostname `db`.

## Demo walkthrough

### 1. Scripted scenarios

`demo/scripts/run_demo.py` submits and evaluates the fixtures in `demo/fixtures/`, then runs four extra checks: kill switch, duplicate webhook, self-approval, and a rolled-back audit-tampering test.

```bash
# Docker
docker compose exec app python demo/scripts/run_demo.py

# Local process (point it at your app and database)
DEMO_BASE_URL=http://127.0.0.1:8000 python demo/scripts/run_demo.py
```

Expected results:

| Scenario | Fixture | Expected outcome |
| --- | --- | --- |
| 01 | Low-risk app change, tests passed, rollback plan | `READY_TO_SHIP` / `AUTO_CLEAR` |
| 02 | Mock AI confidence 0.55 (warning band) | `CAB_REVIEW_REQUIRED` |
| 03–06 | Public `0.0.0.0/0`, prod DB delete, IAM wildcard, `DROP TABLE` | `BLOCKED` / `HARD_BLOCK` (mandatory rules) |
| 07 | Breaking API change to production (score 65, HIGH) | `CAB_REVIEW_REQUIRED` |
| 08–10 | Fabricated evidence, confidence 0.15, `terraform destroy` advice | `BLOCKED` / `HARD_BLOCK` (gate failures) |
| 11 | Inconsistent primary vs. secondary AI opinion | `CAB_REVIEW_REQUIRED` (Gate 5 warning) |
| 12 | Kill switch active during an otherwise auto-clearing change | `CAB_REVIEW_REQUIRED` |
| 13 | Same GitHub webhook delivered twice | first `201`, replay `200`, no duplicate |
| 14 | Submitter tries to approve their own change | `403` |
| 15 | Audit row edited inside a transaction that is rolled back | `is_valid=False` during the edit, `True` after |

Scenarios 2, 8–11 use `metadata._demo` flags that only the mock provider reads. They simulate AI failure modes; they are not real model behavior.

Actual output from a local run (app started with Uvicorn on the host, against PostgreSQL 16 in a container):

![Captured output of the demo script](images/demo-scenario-run-output.png)

The fixture `change_id`s are fixed. A second run against the same database prints `HTTP 409 … already evaluated` for scenarios that were already evaluated, which is expected. Run `docker compose down -v` to start fresh.

### 2. Manual API walkthrough

This walkthrough submits a breaking API change, evaluates it, shows that the submitter can't approve it, and has a second person approve it. Use Bash; replace `B` with your base URL.

```bash
B=http://localhost:8000
DEV=(-H "X-ChangeGuard-Actor: dev.alice" -H "X-ChangeGuard-Role: developer")

# 1. Submit (expect HTTP 201, state PROPOSED)
curl -s -X POST $B/api/v1/changes "${DEV[@]}" -H "Content-Type: application/json" -d '{
  "change_id": "walkthrough-01", "repository": "org/orders-api", "branch": "feature/v2-contract",
  "commit_sha": "abc1234", "author": "dev.alice", "change_type": "api_contract",
  "changed_files": ["openapi/orders.yaml"], "environment_target": "production",
  "has_rollback_plan": true, "tests_passed": true,
  "service_dependencies": ["billing", "shipping"], "metadata": {"breaking_change": true}}'

# 2. Evaluate
curl -s -X POST $B/api/v1/changes/walkthrough-01/evaluate "${DEV[@]}"

# 3. Submitter tries to approve (expect HTTP 403)
curl -s -X POST $B/api/v1/changes/walkthrough-01/cab/approve -H "Content-Type: application/json" \
  -H "X-ChangeGuard-Actor: dev.alice" -H "X-ChangeGuard-Role: approver" -d '{"rationale": "self"}'

# 4. A different approver approves
curl -s -X POST $B/api/v1/changes/walkthrough-01/cab/approve -H "Content-Type: application/json" \
  -H "X-ChangeGuard-Actor: bob.cab" -H "X-ChangeGuard-Role: approver" \
  -d '{"rationale": "Consumers notified; deprecation window agreed"}'

# 5. Verify the audit chain
curl -s $B/api/v1/audit/verify
```

Results observed in a local run:

| Step | Result |
| --- | --- |
| 2 | `state=CAB_REVIEW_REQUIRED`, score **65**, level **HIGH**, rules `RISK-API-001` + `RISK-ENV-001`, all five gates `PASSED`, policy `POL-HIGH-001` |
| 3 | HTTP **403**, `"submitter cannot approve or reject their own change"` |
| 4 | `state=READY_TO_SHIP` |
| Re-running step 2 | HTTP **409**, `invalid transition: READY_TO_SHIP -> RISK_EVALUATED` |
| 5 | `{"is_valid": true, …}` |

Other useful calls: `GET /api/v1/changes?state=BLOCKED`, `GET /api/v1/changes/{id}/cab-brief`, `GET /api/v1/system/status`. To switch the kill switch on or off, use `POST /api/v1/admin/kill-switch/activate` or `/deactivate` with role `admin` and body `{"reason": "…"}`. Any other role gets HTTP 403.

### 3. Dashboard

After the demo, `/dashboard` shows counts by state, the recent risk distribution, the CAB queue, recent changes, and the kill-switch and audit-chain status. It is read-only. CAB decisions are made through the API.

![Dashboard after the demo run](images/dashboard-after-demo-run.png)

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `docker compose build` fails with `CERTIFICATE_VERIFY_FAILED` during `pip install` | Your network inspects TLS. Put your organization's root CA (`.crt`, PEM) in `certs/`, which is git-ignored, and rebuild. The Dockerfile already trusts certificates in that folder |
| `port is already allocated` for 8000 or 5432 | Another service is using the port. Stop it, or run the app locally on another port (`uvicorn … --port 8010`) and point PostgreSQL elsewhere via `CHANGEGUARD_DATABASE_URL` |
| `app` never starts in Compose | Check `docker compose logs migrate`. The app waits for the migration job to finish successfully |
| `/ready` returns 500 | The database is unreachable or has no schema. Check `CHANGEGUARD_DATABASE_URL` and run `alembic upgrade head` |
| Local run can't reach host `db` | `.env` points to the Compose hostname. Export `CHANGEGUARD_DATABASE_URL` with `localhost` |
| `401` on POST endpoints | Missing or invalid `X-ChangeGuard-Actor` / `X-ChangeGuard-Role` headers. Valid roles: `developer`, `operator`, `approver`, `security_reviewer`, `admin` |
| `409` on evaluate or approve | The change isn't in a state that allows that transition, for example it was already evaluated |
| `422` on evaluate | The primary AI provider failed, and the change was blocked (fail closed). With `external`, check the URL and key |
| `413` | The request is larger than `CHANGEGUARD_MAX_PAYLOAD_BYTES` |
| Demo script very slow on Windows with `localhost` | Use `http://127.0.0.1:<port>` for `DEMO_BASE_URL` to avoid IPv6 lookup delays |
