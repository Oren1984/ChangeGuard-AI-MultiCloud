# AI Assurance and Governance

## Trust boundary

The AI provider (`src/ports/ai_provider.py`) produces exactly one thing: an
`AIAssessment` — a summary, an impact map, dependency/rollback considerations, a CAB
executive brief, recommended reviewer roles, referenced evidence, an advisory
`recommended_route`, a suggested risk level, and a confidence score. That's it. There
is no code path anywhere in this repository by which an `AIAssessment` can:

- merge code, approve itself, or execute a deployment,
- modify cloud infrastructure or call a cloud SDK,
- run a shell command,
- or override the deterministic risk engine or the routing decision.

The clearest evidence of the last point: `route_decision()`
(`src/application/routing/decision_router.py`) has the signature
`route_decision(ctx: RoutingContext) -> RoutingDecision`, and `RoutingContext` **does
not have a field for the AI's recommendation at all**. This is locked in by
`tests/unit/test_decision_router.py::test_ai_recommendation_cannot_override_hard_block`,
which asserts the function's parameter list directly. The AI's opinion is surfaced to
humans (CAB brief, dashboard) and nowhere else.

## The five mandatory gates

Every AI response passes through `run_gate_pipeline()`
(`src/application/evaluation/gate_pipeline.py`), in order:

1. **Schema** (`schema_gate.py`) — re-validates the response against a strict Pydantic
   model (`extra="forbid"`, `confidence` bounded to `[0,1]`, `recommended_route` and
   `suggested_risk_level` constrained to known literals). Dataclasses don't enforce
   value ranges at construction time, so this catches an out-of-range or malformed
   value a misbehaving provider could otherwise smuggle through.
2. **Grounding** (`grounding_gate.py`) — every item in `referenced_evidence` must
   match something actually present on the `ChangeRequest` (a changed file, the
   repository/branch, a Terraform resource address, a migration statement prefix, or a
   declared dependency). No evidence at all → `WARNING` (mandatory review). Evidence
   that doesn't match anything real → `FAILED` (fabrication is a hard stop, not a
   review prompt).
3. **Confidence** (`confidence_gate.py`) — configurable thresholds
   (`CHANGEGUARD_CONFIDENCE_APPROVAL_THRESHOLD=0.70`,
   `CHANGEGUARD_CONFIDENCE_HARD_FLOOR=0.35` by default). Above the approval threshold:
   `PASSED`. Between the floor and the threshold: `WARNING`. Below the floor: `FAILED`.
4. **Safety** (`safety_gate.py`) — a categorical keyword blocklist across every text
   field the AI produced (`terraform destroy`, `disable audit`, `bypass approval`,
   `drop database`, `rm -rf`, `ignore failed tests`, ...). Any hit is `FAILED`,
   independent of confidence or risk level.
5. **Consistency** (`consistency_gate.py`) — compares the primary opinion against a
   second, independently-invoked opinion (see "why two calls" below). A materially
   different route, risk level, >0.30 confidence delta, or <50% evidence overlap
   produces `WARNING` (mandatory human review) — it never silently auto-clears.

If Gate 1 fails, Gates 2-4 are recorded as `SKIPPED` (a structurally invalid response
can't be meaningfully evaluated for grounding/confidence/safety) — but Gate 5 still
runs, since it's a structural comparison independent of either individual response's
schema validity. Every gate's result — including `SKIPPED` — is persisted separately in
`gate_results`, so the audit trail always shows exactly what ran and why.

### Why two AI calls per evaluation

`EvaluationPipeline` always calls both a primary and a secondary `AIProvider`. By
default both are the deterministic `MockAIProvider` (the secondary constructed with
`drift=True`), so in the normal case both opinions match and Gate 5 passes cleanly —
this is what "compare two deterministic Mock-provider responses" (per the assurance
requirements) looks like in practice. A demo/test hook
(`change.metadata["_demo"] = "inconsistent"`) makes the drift-mode secondary produce a
materially different opinion on purpose, to exercise Gate 5 without needing two real,
independently-nondeterministic model providers. If the secondary provider itself is
unavailable, that's logged and Gate 5 is `SKIPPED` (non-fatal) — the primary opinion
still stands and the rest of the pipeline proceeds normally.

## Fail-closed behavior

The pipeline fails closed, not open, whenever:

- the **primary** AI provider raises `AIProviderError` (timeout, outage, unparsable
  response) — the change is force-transitioned to `BLOCKED` and the failure is audited
  as `PIPELINE_FAILURE_BLOCKED`;
- an assurance gate returns `FAILED` — the router maps this straight to `HARD_BLOCK`
  (`POL-GATE-FAIL-001`), regardless of risk level;
- the kill switch is active — no AI-assisted change may `AUTO_CLEAR`, full stop;
- required evidence (rollback plan, maintenance window) is missing for an otherwise
  low/medium-risk change — routed to `CAB_REVIEW_REQUIRED`, never auto-cleared.

## Kill switch

`src/domain/policies/kill_switch_policy.py` + `KillSwitchUseCase`. Only the `admin`
role may activate/deactivate it (enforced in the use case, not just the API layer).
`EvaluationPipeline` checks it **twice**: once before calling the AI provider, and
again immediately before the final routing decision — so an activation that happens
mid-evaluation (between those two checks) still catches the change before it can
auto-clear. `tests/assurance/test_pipeline_assurance.py::test_kill_switch_activated_between_stages_blocks_auto_clear`
proves this with a kill-switch repository stub that flips the state exactly between
the two checks. Every activation, deactivation, and every decision it affects is
audited.

## Regression expectations

`MockAIProvider` is a pure function of the `ChangeRequest` (hashing `change_id` +
provider name for its confidence value), so the same change always produces the same
advisory output across runs — this is what makes the assurance test suite
deterministic and CI-stable without mocking a mock.

## Known limitations

- The Mock provider's "reasoning" is template-based, not a real model — it's a
  faithful stand-in for exercising the assurance pipeline, not a claim about real LLM
  behavior.
- The demo-scenario hooks (`change.metadata["_demo"]`) are a POC testing convenience
  and would not exist in a production provider.
- Gate 5's secondary opinion, by default, comes from the same provider family as the
  primary (see above) — a production deployment comparing two genuinely independent
  models would need two real `AIProvider` implementations.

## Human-control boundaries

A human (via CAB approve/reject) is the only path from `CAB_REVIEW_REQUIRED` to a
terminal state, and separation of duties is enforced in the use case
(`CabDecisionUseCase`) itself, not just at the UI: the submitter identity is fixed to
the authenticated actor at submission time (never a client-supplied field) and checked
against the approving actor on every decision. See `docs/CAB_WORKFLOW.md`.
