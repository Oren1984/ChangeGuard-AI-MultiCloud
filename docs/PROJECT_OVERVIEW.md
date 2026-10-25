# Project Overview

**ChangeGuard AI MultiCloud** is a proof-of-concept change-risk and release-governance service. It scores a proposed change with deterministic rules, gets an advisory AI opinion, checks that opinion with five validation gates, and routes the change to one of three outcomes: auto-clear, human (CAB) review, or hard block. Every step is written to a tamper-evident audit log.

It is part of my **System Design & Architecture** portfolio. The focus is the design: clear layering, a pure decision function, fail-closed behavior, and explicit trust boundaries around AI output. It is not a production-ready platform.

## The problem

Many production incidents start with a change: a Terraform plan that opens a security group to `0.0.0.0/0`, a migration that drops a table, an IAM policy with a wildcard. Teams try to catch these through Change Advisory Board (CAB) review. Manual review is slow and inconsistent, and most CI pipelines don't encode "is this change safe to ship?"

AI can summarize a change and draft a review brief quickly. But it can also invent evidence, misjudge severity, or suggest unsafe actions. This project explores one way to use AI as a helper without letting it make the decision.

## Intended users

The design targets these roles, which map to the actor roles in the code (`developer`, `operator`, `approver`, `security_reviewer`, `admin`):

- **Engineers or CI pipelines** that submit a change for evaluation.
- **CAB approvers and security reviewers** who decide on changes routed to human review.
- **Platform or governance admins** who can switch AI-assisted auto-clearing off with a kill switch.
- **Reviewers of this portfolio** who want to see how the controls are put together.

## Purpose and practical value

- Turns change-risk policy into **explicit, testable rules** instead of reviewer intuition.
- Shows a pattern where **AI is advisory only**: the routing function never receives the AI's recommended route as an input.
- Sends only the changes that need human judgment to people, and records why.
- Keeps an **audit trail that shows tampering**: each record is linked to the previous one by a SHA-256 hash.

## Implemented capabilities

| Capability | Status |
| --- | --- |
| REST API for submitting, evaluating, listing, and reading changes (FastAPI) | Implemented |
| Deterministic risk engine: 16 rules, score 0–100, LOW / MEDIUM / HIGH / CRITICAL | Implemented |
| Advisory AI assessment from an offline, deterministic `MockAIProvider` | Implemented (simulated AI) |
| Second AI opinion (the same mock in "drift" mode) used for the consistency check | Implemented (simulated) |
| Five assurance gates: schema, grounding, confidence, safety, consistency | Implemented |
| Pure decision router: `AUTO_CLEAR`, `CAB_REVIEW_REQUIRED`, `HARD_BLOCK` | Implemented |
| Change state machine with an explicit list of allowed transitions | Implemented |
| CAB approve/reject with separation of duties (a submitter can't decide their own change) | Implemented |
| Admin-only kill switch that disables auto-clear | Implemented |
| SHA-256 hash-chained audit log and a `/api/v1/audit/verify` endpoint | Implemented |
| GitHub/GitLab webhook intake that is idempotent on replay | Implemented for **simulated** payloads only |
| Read-only HTML dashboard, `/health`, `/ready`, Prometheus `/metrics` | Implemented |
| Docker Compose stack: PostgreSQL 16, Alembic migration job, app, optional Prometheus | Implemented |
| `ExternalAIProvider` adapter (HTTP, OpenAI-style JSON) | Optional, off by default, never tested against a real endpoint |
| AWS and GCP Terraform | Reference only. CI runs `fmt`/`validate`; nothing is ever applied |

## Main workflow

1. **Intake.** A change is submitted as normalized JSON (`POST /api/v1/changes`) or as a simulated GitHub/GitLab webhook (`POST /api/v1/webhooks/{provider}`). It starts in the `PROPOSED` state. The submitter's identity comes from the `X-ChangeGuard-Actor` header, not from the request body.
2. **Evaluation** (`POST /api/v1/changes/{id}/evaluate`):
   1. The risk engine runs all rules and produces a score, a level, and the evidence behind them.
   2. The primary AI provider writes an advisory summary, and the secondary provider gives a second opinion.
   3. The five gates validate the primary AI response.
   4. The service reads the kill-switch state.
   5. The pure router picks one outcome. The change moves to `READY_TO_SHIP`, `CAB_REVIEW_REQUIRED` (and a CAB ticket is created), or `BLOCKED`.
3. **Human review.** An approver who did not submit the change approves (→ `READY_TO_SHIP`) or rejects (→ `BLOCKED`) it.
4. **Audit.** Every step appends a hash-chained audit record, and anyone can verify the chain.

`READY_TO_SHIP` is only a governance state. The system never deploys, merges, or calls a cloud API.

## Scope boundaries

**In scope:** change-risk evaluation, AI-output validation, routing, the CAB decision trail, the kill switch, audit integrity, local Docker deployment, and reference Terraform.

**Out of scope (not implemented):**

- Real authentication. Identity comes from two request headers. Read endpoints need no headers at all.
- Real VCS integration. The service does not call GitHub or GitLab, and it does not verify webhook signatures.
- A real LLM. The default and the tested path both use the deterministic mock.
- Deployment or rollback execution, and background workers or queues.
- Any running cloud environment.

## Concrete example

Demo fixture `03_terraform_public_exposure.json` submits a production Terraform plan that changes `aws_security_group.web` to allow `0.0.0.0/0`. In a local run:

- Rule `RISK-NET-001` (severity 95, mandatory in production) and `RISK-ENV-001` (production target, severity 10) trigger. The score is capped at **100**, and the level is **CRITICAL**.
- The mock AI produces a grounded summary, and all five gates pass. That doesn't matter here, because the router checks mandatory rules first.
- The router returns **`HARD_BLOCK`** with policy `POL-CRITICAL-001`, and the change ends in **`BLOCKED`**.
- The response lists the required action: *"Restrict CIDR ranges to approved network segments before deployment."*

Compare demo fixture `07_high_risk_requires_cab.json`: a breaking API contract change to production scores 65 (**HIGH**) with no mandatory rule. It goes to CAB review. In the local run it was then approved by `approver.demo`, a different actor from the submitter, and moved to `READY_TO_SHIP`.

![Dashboard after a local demo run](images/dashboard-after-demo-run.png)

*Real screenshot of `/dashboard` after running the demo script locally, plus one manual CAB approval of `demo-07-high-risk-cab`.*

## Related documents

- [ARCHITECTURE.md](ARCHITECTURE.md): components, data flow, deployment, and design tradeoffs.
- [DEMO_AND_OPERATIONS.md](DEMO_AND_OPERATIONS.md): setup, running the stack, demo walkthrough, and troubleshooting.
- [GOVERNANCE_AND_VALIDATION.md](GOVERNANCE_AND_VALIDATION.md): oversight, security controls, tests, and limitations.
