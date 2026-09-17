from __future__ import annotations

import copy

from tests.security.conftest import VALID_CHANGE_PAYLOAD, actor_headers


def test_missing_actor_headers_rejected(client):
    resp = client.post("/api/v1/changes", json=VALID_CHANGE_PAYLOAD)
    assert resp.status_code == 401


def test_invalid_role_header_rejected(client):
    resp = client.post(
        "/api/v1/changes",
        json=VALID_CHANGE_PAYLOAD,
        headers=actor_headers("dev.one", "superadmin"),
    )
    assert resp.status_code == 401


def test_unauthorized_kill_switch_change_rejected(client):
    resp = client.post(
        "/api/v1/admin/kill-switch/activate",
        json={"reason": "trying to escalate"},
        headers=actor_headers("dev.one", "developer"),
    )
    assert resp.status_code == 403


def test_admin_can_change_kill_switch(client):
    resp = client.post(
        "/api/v1/admin/kill-switch/activate",
        json={"reason": "incident response"},
        headers=actor_headers("admin.one", "admin"),
    )
    assert resp.status_code == 200
    assert resp.json()["active"] is True


def _high_risk_payload(change_id: str) -> dict:
    # HIGH (not CRITICAL) risk by design: a breaking API change to production
    # scores 65 (RISK-API-001=55 + RISK-ENV-001=10), landing in the HIGH
    # band (50-79) so it forces CAB review without tripping a mandatory
    # (severity >= 90) hard-block rule.
    return dict(
        VALID_CHANGE_PAYLOAD,
        change_id=change_id,
        change_type="api_contract",
        environment_target="production",
        metadata={"breaking_change": True},
    )


def test_self_approval_is_rejected(client):
    payload = _high_risk_payload("chg-sec-self-approve")
    headers = actor_headers("dev.one", "developer")
    submit = client.post("/api/v1/changes", json=payload, headers=headers)
    assert submit.status_code in (200, 201)

    evaluate = client.post(f"/api/v1/changes/{payload['change_id']}/evaluate", json=None, headers=headers)
    assert evaluate.status_code == 200
    assert evaluate.json()["state"] in ("CAB_REVIEW_REQUIRED",)

    approve = client.post(
        f"/api/v1/changes/{payload['change_id']}/cab/approve",
        json={"rationale": "looks fine to me"},
        headers=actor_headers("dev.one", "approver"),  # same actor as submitter
    )
    assert approve.status_code == 403


def test_self_approval_rejected_even_when_payload_author_differs_from_caller(client):
    # Regression test: submitted_by must be taken from the authenticated
    # actor header, never from a client-supplied "author"/"submitted_by"
    # field, or self-approval prevention can be trivially bypassed by
    # submitting under a different declared author.
    payload = _high_risk_payload("chg-sec-spoofed-author")
    payload["author"] = "someone.else"
    submit_headers = actor_headers("dev.one", "developer")
    client.post("/api/v1/changes", json=payload, headers=submit_headers)
    client.post(f"/api/v1/changes/{payload['change_id']}/evaluate", json=None, headers=submit_headers)

    approve = client.post(
        f"/api/v1/changes/{payload['change_id']}/cab/approve",
        json={"rationale": "self-approving via spoofed author field"},
        headers=actor_headers("dev.one", "approver"),
    )
    assert approve.status_code == 403


def test_different_approver_can_approve(client):
    payload = _high_risk_payload("chg-sec-real-approve")
    headers = actor_headers("dev.one", "developer")
    client.post("/api/v1/changes", json=payload, headers=headers)
    client.post(f"/api/v1/changes/{payload['change_id']}/evaluate", json=None, headers=headers)

    approve = client.post(
        f"/api/v1/changes/{payload['change_id']}/cab/approve",
        json={"rationale": "reviewed and approved"},
        headers=actor_headers("approver.two", "approver"),
    )
    assert approve.status_code == 200
    assert approve.json()["state"] == "READY_TO_SHIP"


def test_oversized_payload_is_rejected(client):
    huge_diff = "x" * 2_000_000
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-sec-huge", diff=huge_diff)
    resp = client.post("/api/v1/changes", json=payload, headers=actor_headers("dev.one", "developer"))
    assert resp.status_code in (413, 422)


def test_xss_and_sqli_strings_are_stored_as_inert_data(client):
    payload = copy.deepcopy(VALID_CHANGE_PAYLOAD)
    payload["change_id"] = "chg-sec-injection"
    payload["changed_files"] = ["<script>alert(1)</script>.py"]
    payload["diff"] = "'; DROP TABLE changes; --"
    resp = client.post("/api/v1/changes", json=payload, headers=actor_headers("dev.one", "developer"))
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body["changed_files"] == ["<script>alert(1)</script>.py"]

    fetched = client.get(f"/api/v1/changes/{payload['change_id']}")
    assert fetched.status_code == 200


def test_duplicate_submission_is_idempotent(client):
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-sec-dup")
    headers = actor_headers("dev.one", "developer")
    first = client.post("/api/v1/changes", json=payload, headers=headers)
    second = client.post("/api/v1/changes", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["change_id"] == second.json()["change_id"]


def test_invalid_state_transition_rejected(client):
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-sec-double-eval")
    headers = actor_headers("dev.one", "developer")
    client.post("/api/v1/changes", json=payload, headers=headers)
    first = client.post(f"/api/v1/changes/{payload['change_id']}/evaluate", json=None, headers=headers)
    assert first.status_code == 200

    second = client.post(f"/api/v1/changes/{payload['change_id']}/evaluate", json=None, headers=headers)
    assert second.status_code == 409


def test_error_responses_never_leak_internals(client):
    resp = client.get("/api/v1/changes/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "Traceback" not in body["detail"]
    assert "correlation_id" in body


def test_unknown_fields_are_rejected_by_strict_schema(client):
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-sec-strict", unexpected_field="nope")
    resp = client.post("/api/v1/changes", json=payload, headers=actor_headers("dev.one", "developer"))
    assert resp.status_code == 422
