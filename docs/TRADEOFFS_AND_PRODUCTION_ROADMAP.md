# Tradeoffs and Production Roadmap

## POC decisions and rejected alternatives

| Decision | Rejected alternative | Why |
|---|---|---|
| Modular monolith | Microservices (separate risk/AI/gate/routing services) | The evaluation pipeline is one coherent unit of work with no independent scaling or deployment need at this scope; microservices would add network calls, partial-failure handling, and eventual consistency for zero benefit here. |
| Synchronous pipeline | Async worker + queue (Celery/SQS/etc.) | Simpler to test end-to-end and to reason about ordering (the two kill-switch checks, the gate sequence); appropriate for a POC's request volume. Flagged below for production. |
| Header-based actor identity | Full OIDC integration | Out of scope for demonstrating the governance logic itself; the separation-of-duties and role checks are fully real and tested, just anchored to a documented, weaker identity boundary. |
| In-database SHA-256 hash chain | External WORM storage / ledger anchoring | Proves the tamper-evidence concept (and is genuinely tested to detect mutation/deletion) without standing up an external ledger service for a POC. |
| JSONB evidence columns | Fully normalized evidence tables | Evidence is written once and read as a whole unit; normalizing would add migration and query complexity with no corresponding query pattern that needs it. |
| Single Postgres instance, no read replicas | Multi-AZ / read replicas | Unnecessary at POC scale; the Terraform references note where to add this (`multi_az`, Cloud SQL HA) for production. |

## Modular monolith justification

Clean Architecture's dependency-inversion boundaries (`domain` → `application` →
`ports`/`adapters` → `api`) are exactly what makes a later extraction to services
possible *if it's ever actually needed* — the risk engine, the gates, and the router
are already pure functions with no framework coupling. Splitting prematurely would add
operational cost today for an option that's already preserved architecturally.

## Header-based identity limitation

`X-ChangeGuard-Actor`/`X-ChangeGuard-Role` are trusted as-is once
character/length-validated. There is no cryptographic proof the header wasn't set by
an untrusted client. **Production path**: OIDC/OAuth2 against an enterprise IdP,
signed/verified JWTs carrying role claims, and mTLS between any internal service
callers. The separation-of-duties and role-authorization *logic* in this repo does not
change — only the identity source feeding `ActorContext` does.

## In-database audit-chain limitation

SHA-256 hash chaining detects retroactive mutation and record deletion (both are
integration-tested), but someone with direct database superuser access could, in
principle, rewrite the entire chain consistently from scratch. **Production path**:
periodically anchor chain checkpoints to an external, append-only store (S3 Object
Lock/WORM, AWS QLDB, or a public ledger), so even a full database compromise can't
retroactively rewrite history undetected.

## Synchronous processing limitation

The full risk→AI→gates→routing pipeline runs inline within the `POST
/changes/{id}/evaluate` request. This is fine for the demonstrated volume but doesn't
scale to a high-throughput CI/CD gate. **Production path**: move `EvaluationPipeline`
execution behind a queue (SQS/Cloud Tasks/etc.) with a worker pool, and have the API
return `202 Accepted` + a status-poll or webhook-callback pattern. The pipeline's
internal structure (repository ports, pure gates/router) does not need to change for
this — only the orchestration entry point.

## Other production-hardening items

- **OIDC/OAuth2 + mTLS**: see above.
- **WORM/ledger audit anchoring**: see above.
- **Private networking end-to-end**: both Terraform references already keep the
  database private; a production rollout should also front the API with a WAF and
  restrict egress from the compute layer to only what's needed (Secrets
  Manager/Secret Manager, the database, and an external AI provider if enabled).
- **Scalability**: horizontal scaling of the `app` service is already stateless and
  safe (all state lives in PostgreSQL); the audit-append `SELECT ... FOR UPDATE` lock
  is the one serialization point to watch under high write concurrency.
- **Disaster recovery**: enable RDS Multi-AZ / Cloud SQL HA, real backup retention and
  a tested restore runbook, and `skip_final_snapshot=false` /
  `deletion_protection=true` before any production use of either Terraform reference.
