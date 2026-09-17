# Trilogy Positioning

ChangeGuard AI belongs to a three-part Enterprise AI Governance architecture. The three
systems intentionally share a philosophy while owning strictly separate business
responsibilities.

## The three systems

- **ChangeGuard AI** (this repository) — governs a proposed change **before** it
  reaches production: is this change safe and sufficiently governed to progress toward
  deployment?
- **ArchGuard AI** — operates **during** a live incident: runtime incident response and
  operational resilience once something is already running in production.
- **PolicyGuard AI** (future) — operates **continuously after** deployment: ongoing
  policy, configuration-drift, and compliance governance for what's already live.

```
   PRE-DEPLOYMENT              RUNTIME                  POST-DEPLOYMENT (continuous)
  ┌───────────────┐      ┌─────────────────┐          ┌───────────────────┐
  │  ChangeGuard   │ ──▶ │    ArchGuard     │  ──────▶ │    PolicyGuard      │
  │  AI            │      │    AI            │          │    AI (future)      │
  │  "Is this      │      │  "What's wrong    │          │  "Is everything      │
  │  change safe    │      │  right now, and   │          │  still compliant     │
  │  to ship?"      │      │  how do we         │          │  and drift-free?"    │
  │                │      │  respond?"        │          │                     │
  └───────────────┘      └─────────────────┘          └───────────────────┘
```

## Shared architectural principles

All three are built on the same non-negotiable foundations:

- **Deterministic decision gates** — a non-AI, rule-based engine is always the
  authority for anything that blocks or forces an outcome; AI is advisory.
- **Fail-closed behavior** — any ambiguity, outage, or validation failure defaults to
  the safe/blocked state, never to silent progress.
- **Human-in-the-loop governance** — high-stakes decisions require a human approval
  step with enforced separation of duties.
- **Interchangeable AI providers** — every AI integration sits behind a `Protocol`-style
  abstraction; no system is married to one model vendor.
- **Strict schemas** — every AI output is validated against an explicit contract before
  it's trusted for anything.
- **Tamper-evident auditability** — every governance decision is recorded in a
  verifiable, hash-chained log.
- **Multi-cloud portability** — no direct cloud SDK dependency in core business logic.
- **Clean Architecture** — domain logic stays pure and framework-independent.
- **No direct destructive execution** — none of the three systems lets AI (or even an
  automated pipeline) run a destructive command or cloud action directly; a human or an
  explicit, deterministic policy authorizes every consequential action.

## Why they intentionally overlap in philosophy but not in responsibility

Sharing a philosophy means an engineer who understands one system's assurance-gate
pattern, audit-chain design, or kill-switch semantics already understands the shape of
the other two — that consistency is deliberate and valuable across a governance
portfolio. But the three systems answer *fundamentally different questions* with
*fundamentally different inputs and outputs*, and merging their responsibilities would
produce a single sprawling system that's worse at all three jobs than three focused
ones are at their own.

## Input / decision / output comparison

| | ChangeGuard AI | ArchGuard AI | PolicyGuard AI (future) |
|---|---|---|---|
| **Primary input** | A proposed change (code/infra/config/migration) | A live incident/anomaly signal | Continuous state of deployed infrastructure/policy |
| **Timing** | Before deployment | During an active incident | Continuously, post-deployment |
| **Core question** | Is this change safe enough to ship? | What's happening right now, and how should we respond? | Is what's running still compliant and drift-free? |
| **Decision output** | `AUTO_CLEAR` / `CAB_REVIEW_REQUIRED` / `HARD_BLOCK` | Recommended/authorized incident response actions | Drift/violation findings + required remediation |
| **Human control point** | CAB approve/reject | Incident commander authorization | Compliance owner sign-off on remediation |
| **AI's role** | Advisory impact summary, never authoritative for routing | Advisory diagnosis/response suggestions, never authoritative for destructive action | Advisory drift/risk summary, never authoritative for auto-remediation |

## Domain boundaries

ChangeGuard never reacts to a live incident and never continuously audits already-
deployed infrastructure — those are ArchGuard's and PolicyGuard's jobs respectively.
Conversely, neither of those systems evaluates a *proposed* change before it exists in
production. A change that ChangeGuard `AUTO_CLEAR`s and that later causes an incident
is squarely ArchGuard's problem; a change that ChangeGuard approves but that later
drifts out of compliance is squarely PolicyGuard's problem. Each system's audit trail
is its own — there is no shared database or shared decision authority between them,
only a shared architectural philosophy.
