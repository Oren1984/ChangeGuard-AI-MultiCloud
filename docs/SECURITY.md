# Security

## Threat model and trust boundaries

| Boundary | Trust level | Notes |
|---|---|---|
| Inbound HTTP request | Untrusted | Strict Pydantic schemas (`extra="forbid"`), size limits, correlation IDs |
| `X-ChangeGuard-Actor`/`X-ChangeGuard-Role` headers | Weakly trusted | Explicit POC boundary — see "Authentication limitations" |
| AI provider output (`AIAssessment`) | **Fully untrusted** | Must pass all 5 assurance gates before influencing anything; never influences routing at all |
| VCS webhook payload | Untrusted | Normalized through a `VCSProvider` adapter; strict field extraction, no `eval`/dynamic parsing |
| Database contents | Trusted (own writes only) | Parameterized queries throughout; JSONB fields hold structured, non-executable evidence |

## Authentication/authorization limitations (explicit POC boundary)

Actor identity is two plain headers, validated for character set and length
(`src/security/actor_context.py`) and mapped to a fixed `ActorRole` enum. This is
**not** production-grade identity — there is no signature, no token, no session. It is
sufficient to demonstrate role-based authorization and separation of duties correctly,
and is documented as a boundary to replace, not a gap to hide. See
`docs/TRADEOFFS_AND_PRODUCTION_ROADMAP.md` for the OIDC/OAuth2/mTLS roadmap.

Enforced today, in the domain/application layer (not just at the API edge):

- Only `admin` may change kill-switch state (`can_change_kill_switch`).
- Only `approver`/`security_reviewer`/`admin` may record a CAB decision, and never the
  submitter (`can_decide_cab_ticket`) — see `docs/CAB_WORKFLOW.md`.

## Input validation

- Every request body is a strict Pydantic v2 model with `extra="forbid"` — unknown
  fields are rejected outright (`tests/security/test_api_security.py::test_unknown_fields_are_rejected_by_strict_schema`).
- Explicit size caps: `changed_files` (2000 items), `migration_statements` (500),
  `service_dependencies` (200), `diff` (500,000 chars) at the schema level, plus a
  global request-body byte cap (`CHANGEGUARD_MAX_PAYLOAD_BYTES`, default 1MB) enforced
  in middleware before the body is even parsed.
- XSS/SQL-injection-shaped strings are accepted as inert data and round-tripped
  unexecuted (`tests/security/test_api_security.py::test_xss_and_sqli_strings_are_stored_as_inert_data`)
  — the ORM's parameterized queries mean a string is always just a string.

## Secret handling and logging

- `src/security/redaction.py` scrubs `Bearer <token>` and AWS access-key-shaped
  strings out of any string value, and blanks any dict value whose key looks
  sensitive (`password`, `secret`, `token`, `api_key`, `authorization`, `credential`,
  `private_key`), recursively.
- The structured JSON log formatter (`src/observability/logging.py`) applies
  `redact_value()` to every log message.
- Global exception handlers (`src/main.py`) never return a stack trace or internal
  exception detail to a client — every error response is `{error, detail,
  correlation_id}`, with `detail` also passed through redaction.
- `.env.example` contains placeholders only; `.gitignore` excludes `.env*` (except the
  example) and the local dev-CA cert directory used only for building this image
  behind a corporate TLS-inspecting proxy.

## Container security

- Multi-stage `Dockerfile`; the runtime stage installs only `libpq5` + `curl`, no
  compiler toolchain.
- Runs as a dedicated non-root `changeguard` user (`groupadd`/`useradd --system`).
- `HEALTHCHECK` hits `/health` over `curl`.
- No secrets baked into any image layer — the DB URL and any external AI key are
  injected via environment/Secrets Manager/Secret Manager at deploy time, never
  `COPY`'d in.

## Abuse cases covered by tests

`tests/security/test_api_security.py` and `tests/assurance/test_pipeline_assurance.py`
exercise: missing/invalid actor headers, role escalation attempts, self-approval
(including a spoofed-author variant), oversized payloads, injection-as-inert-data,
duplicate/idempotent submission, invalid state transitions, unauthorized kill-switch
changes, AI fabrication/low-confidence/unsafe-recommendation/inconsistency, and a
simulated AI provider outage.

## No direct execution surfaces

- No code path executes a shell command constructed from model output or request
  input.
- No direct cloud SDK call exists in `domain/` or `application/` code.
- No `eval`/`exec`/dynamic import of untrusted input anywhere in the codebase.
- No unsafe deserialization — all inbound data is parsed through Pydantic, all
  outbound data through explicit response schemas.

## Production-hardening recommendations

See `docs/TRADEOFFS_AND_PRODUCTION_ROADMAP.md` for the full list: OIDC/OAuth2 + IdP +
mTLS in place of header-based identity, WORM/ledger anchoring for the audit chain,
private networking end-to-end, and a real secrets-rotation story.
