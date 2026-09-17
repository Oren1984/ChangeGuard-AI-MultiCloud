# Operations and Observability

## Local operation

```bash
cp .env.example .env
docker compose build
docker compose up -d      # starts db (healthchecked) -> migrate (runs once) -> app
docker compose ps
docker compose logs -f app
docker compose down        # add -v to also drop the DB volume
```

`docker compose up -d` brings up three things in dependency order: `db` (PostgreSQL 16,
healthchecked via `pg_isready`), `migrate` (runs `alembic upgrade head` once and exits),
and `app` (waits for both). An optional `prometheus` service is behind the
`monitoring` Compose profile: `docker compose --profile monitoring up -d`.

## Health and readiness

- `GET /health` — liveness only, always returns `{"status": "ok"}` if the process is up.
- `GET /ready` — readiness; executes `SELECT 1` against PostgreSQL and fails (500) if
  the database is unreachable. The Dockerfile's `HEALTHCHECK` polls `/health`.

## Metrics

`GET /metrics` (Prometheus text format, `prometheus_client`):

| Metric | Type | Labels |
|---|---|---|
| `changeguard_http_errors_total` | Counter | `status_code` |
| `changeguard_evaluation_duration_seconds` | Histogram | — |
| `changeguard_decisions_total` | Counter | `decision` |
| `changeguard_risk_levels_total` | Counter | `level` |
| `changeguard_gate_failures_total` | Counter | `gate` |
| `changeguard_ai_provider_failures_total` | Counter | `provider`, `reason` |
| `changeguard_cab_queue_size` | Gauge | — |

`monitoring/prometheus.yml` scrapes `app:8000/metrics` every 15s when the monitoring
profile is enabled.

## Logs

Structured JSON via `python-json-logger`
(`src/observability/logging.py`): every log line carries `asctime`, `levelname`,
`name`, `correlation_id`, and `message`. A logging filter both attaches the current
request's correlation ID and redacts secret-shaped substrings
(`src/security/redaction.py`) from the message before it's ever written out.

## Correlation IDs

Every request gets an `X-Correlation-ID` (reused if the client already sent one),
stored in a `contextvar` for the duration of the request
(`src/observability/correlation.py`), attached to every log line emitted during that
request, and echoed back in the response header and in every structured error body
(`{error, detail, correlation_id}`).

## Failure handling

- Unhandled exceptions never leak a stack trace or internal detail — the global
  exception handler in `src/main.py` returns a generic `internal_error` with the
  correlation ID.
- Known domain/application exceptions map to specific, meaningful status codes (see the
  `_ERROR_STATUS_MAP` table in `src/main.py`): `ChangeNotFoundError` → 404,
  `InvalidStateTransitionError` → 409, `SeparationOfDutiesViolationError` → 403,
  `AIProviderError` → 503, `PipelineFailureError` → 422, `AuditPersistenceError` → 500.
- If the primary AI provider is unavailable mid-pipeline, the change is force-blocked
  and the failure is audited — never left in an ambiguous state (see
  `docs/AI_ASSURANCE_AND_GOVERNANCE.md`).

## Backup and recovery considerations

This POC does not implement backup automation. For the reference Terraform:

- AWS: RDS `storage_encrypted=true`; `skip_final_snapshot=true` is a POC
  simplification — set to `false` and enable `multi_az` before any real use.
- GCP: Cloud SQL `backup_configuration.enabled=true` by default;
  `deletion_protection=false` is the same kind of POC simplification.

Neither reference architecture has been applied — see
`docs/MULTI_CLOUD_REFERENCE.md`.

## Kill-switch operation

```bash
curl -X POST http://localhost:8000/api/v1/admin/kill-switch/activate \
  -H "X-ChangeGuard-Actor: admin.oncall" -H "X-ChangeGuard-Role: admin" \
  -H "Content-Type: application/json" -d '{"reason": "incident-1234"}'

curl -X POST http://localhost:8000/api/v1/admin/kill-switch/deactivate \
  -H "X-ChangeGuard-Actor: admin.oncall" -H "X-ChangeGuard-Role: admin" \
  -H "Content-Type: application/json" -d '{"reason": "resolved"}'
```

Only `admin` may call either endpoint; every activation/deactivation is written to the
audit trail with the actor and reason. While active, no AI-assisted change can
`AUTO_CLEAR` — see `docs/AI_ASSURANCE_AND_GOVERNANCE.md` for the two-checkpoint
enforcement detail.
