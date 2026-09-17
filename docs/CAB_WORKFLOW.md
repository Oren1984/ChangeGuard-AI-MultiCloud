# CAB Workflow

## Ticket structure

Built by `build_cab_ticket()` (`src/application/orchestration/cab_ticket_builder.py`)
the moment the router returns `CAB_REVIEW_REQUIRED`, and persisted via `CabRepository`:

| Field | Source |
|---|---|
| `executive_summary` | AI's `cab_executive_brief`, or a deterministic fallback if AI is unavailable |
| `business_impact` | Dependency count + blast-radius description from the risk engine |
| `technical_impact` | Changed-file count + triggered rule IDs |
| `risk_level`, `triggered_controls` | Straight from the `RiskAssessment` |
| `evidence` | Triggered-rule descriptions + AI's grounded `referenced_evidence`, deduplicated |
| `rollback_ready`, `maintenance_window_ready` | From the `ChangeRequest` |
| `required_approver_roles` | Always includes `approver`; adds `security_reviewer` for IAM/Terraform changes; merges in the AI's suggested reviewer roles (filtered to valid `ActorRole` values) |
| `submitted_by` | The **authenticated actor** who called `POST /changes` — never a client-supplied field (see Security notes below) |

## Approval requirements and separation of duties

`CabDecisionUseCase.execute()` (`src/application/use_cases/cab_decision.py`) is the
single path to a CAB decision, called by both `POST /changes/{id}/cab/approve` and
`.../cab/reject`. Before recording anything, it calls
`can_decide_cab_ticket(ticket, actor, role)`
(`src/domain/policies/separation_of_duties.py`), which requires:

1. `actor != ticket.submitted_by` — the submitter can never decide their own change.
2. `role in {approver, security_reviewer, admin}` — `developer`/`operator` cannot
   record a CAB decision at all.

Both checks run in the domain/application layer, not just as a UI restriction — an API
client cannot bypass them by any route. Critically, `submitted_by` is set from the
**authenticated `X-ChangeGuard-Actor` header at submission time**
(`src/api/routes/changes.py`), overriding whatever the request body's `author`/
`submitted_by` field says — otherwise a submitter could spoof a different declared
author and then approve their own change under their real identity. This exact attack
is covered by
`tests/security/test_api_security.py::test_self_approval_rejected_even_when_payload_author_differs_from_caller`.

## State transitions

```
GATES_PASSED --(router: CAB_REVIEW_REQUIRED)--> CAB_REVIEW_REQUIRED
CAB_REVIEW_REQUIRED --(approve)--> CAB_APPROVED --> READY_TO_SHIP   (cascades immediately)
CAB_REVIEW_REQUIRED --(reject)-->  CAB_REJECTED --> BLOCKED          (cascades immediately)
```

There is no separate "finalize" endpoint — approval/rejection immediately cascades to
the terminal state, since no additional gating step exists between a CAB decision and
its consequence in this POC's scope. Both transitions are explicit entries in
`ALLOWED_TRANSITIONS` and validated the same way every other transition is.

## Decision matrix (recap from the router)

| Condition | Outcome |
|---|---|
| CRITICAL risk or a mandatory rule violation | `HARD_BLOCK` (CAB never sees it, unless an explicitly configured critical-exception flag is set) |
| Any assurance gate `FAILED` | `HARD_BLOCK` |
| HIGH risk | `CAB_REVIEW_REQUIRED` |
| Any gate `WARNING` (including AI inconsistency) | `CAB_REVIEW_REQUIRED` |
| Missing rollback plan/maintenance window on an otherwise LOW/MEDIUM change | `CAB_REVIEW_REQUIRED` |
| Kill switch active | `CAB_REVIEW_REQUIRED` (would otherwise have auto-cleared) |
| LOW/MEDIUM risk, all gates passed, evidence complete, kill switch off | `AUTO_CLEAR` |

## Example executive CAB brief

From demo fixture `07_high_risk_requires_cab.json` (a breaking API contract change to
production):

> Executive brief: api_contract change to org/service-d, risk-relevant evidence
> includes 3 item(s). Rollback ready: True.
>
> **Risk level:** HIGH (score 65) · **Triggered controls:** RISK-API-001,
> RISK-ENV-001 · **Business impact:** No declared service dependencies; blast radius
> limited to this component · **Required approvers:** approver
