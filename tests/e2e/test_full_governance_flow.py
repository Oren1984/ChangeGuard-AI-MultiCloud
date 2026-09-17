from __future__ import annotations

from tests.e2e.conftest import VALID_CHANGE_PAYLOAD, actor_headers

GITHUB_WEBHOOK_PAYLOAD = {
    "repository": {"full_name": "org/service-a"},
    "pull_request": {
        "number": 42,
        "head": {"ref": "feature/e2e", "sha": "f" * 40},
        "user": {"login": "dev.one"},
    },
    "files": ["src/app.py", "tests/test_app.py"],
    "diff": "- old\n+ new",
    "changeguard": {
        "change_id": "chg-e2e-webhook",
        "change_type": "application_code",
        "has_rollback_plan": True,
        "environment_target": "staging",
        "tests_passed": True,
    },
}


def test_webhook_intake_through_auto_clear(client):
    headers = actor_headers("ci-bot", "developer")

    intake = client.post("/api/v1/webhooks/github", json=GITHUB_WEBHOOK_PAYLOAD, headers=headers)
    assert intake.status_code == 201
    assert intake.json()["repository"] == "org/service-a"

    evaluate = client.post("/api/v1/changes/chg-e2e-webhook/evaluate", json=None, headers=headers)
    assert evaluate.status_code == 200
    body = evaluate.json()
    assert body["state"] == "READY_TO_SHIP"
    assert body["routing_decision"]["decision"] == "AUTO_CLEAR"
    assert body["risk_assessment"]["level"] == "LOW"
    assert all(g["status"] == "PASSED" for g in body["gate_results"])

    fetched = client.get("/api/v1/changes/chg-e2e-webhook")
    assert fetched.status_code == 200
    assert fetched.json()["state"] == "READY_TO_SHIP"


def test_webhook_replay_is_idempotent(client):
    headers = actor_headers("ci-bot", "developer")
    changeguard_block = dict(GITHUB_WEBHOOK_PAYLOAD["changeguard"], change_id="chg-e2e-replay")
    payload = dict(GITHUB_WEBHOOK_PAYLOAD, changeguard=changeguard_block)

    first = client.post("/api/v1/webhooks/github", json=payload, headers=headers)
    second = client.post("/api/v1/webhooks/github", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 200


def test_full_cab_flow_to_ready_to_ship(client):
    headers = actor_headers("dev.two", "developer")
    payload = dict(
        VALID_CHANGE_PAYLOAD,
        change_id="chg-e2e-cab",
        change_type="api_contract",
        environment_target="production",
        metadata={"breaking_change": True},
    )
    client.post("/api/v1/changes", json=payload, headers=headers)
    evaluate = client.post("/api/v1/changes/chg-e2e-cab/evaluate", json=None, headers=headers)
    assert evaluate.json()["state"] == "CAB_REVIEW_REQUIRED"
    assert evaluate.json()["cab_ticket"] is not None

    approve = client.post(
        "/api/v1/changes/chg-e2e-cab/cab/approve",
        json={"rationale": "reviewed by security"},
        headers=actor_headers("security.one", "security_reviewer"),
    )
    assert approve.status_code == 200
    assert approve.json()["state"] == "READY_TO_SHIP"
    assert approve.json()["cab_ticket"]["decision"] == "APPROVED"


def test_cab_rejection_blocks_the_change(client):
    headers = actor_headers("dev.three", "developer")
    payload = dict(
        VALID_CHANGE_PAYLOAD,
        change_id="chg-e2e-reject",
        change_type="api_contract",
        environment_target="production",
        metadata={"breaking_change": True},
    )
    client.post("/api/v1/changes", json=payload, headers=headers)
    client.post("/api/v1/changes/chg-e2e-reject/evaluate", json=None, headers=headers)

    reject = client.post(
        "/api/v1/changes/chg-e2e-reject/cab/reject",
        json={"rationale": "insufficient evidence"},
        headers=actor_headers("approver.one", "approver"),
    )
    assert reject.status_code == 200
    assert reject.json()["state"] == "BLOCKED"


def test_audit_chain_is_valid_after_a_full_flow(client):
    headers = actor_headers("dev.four", "developer")
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-e2e-audit")
    client.post("/api/v1/changes", json=payload, headers=headers)
    client.post("/api/v1/changes/chg-e2e-audit/evaluate", json=None, headers=headers)

    verification = client.get("/api/v1/audit/verify")
    assert verification.status_code == 200
    body = verification.json()
    assert body["is_valid"] is True
    assert body["total_records"] > 0


def test_system_status_reports_aggregate_state(client):
    headers = actor_headers("dev.five", "developer")
    payload = dict(VALID_CHANGE_PAYLOAD, change_id="chg-e2e-status")
    client.post("/api/v1/changes", json=payload, headers=headers)

    status_resp = client.get("/api/v1/system/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["ai_provider"] == "mock"
    assert body["audit_chain_valid"] is True
    assert "PROPOSED" in body["change_counts_by_state"]


def test_dashboard_renders_without_error(client):
    headers = actor_headers("dev.six", "developer")
    client.post("/api/v1/changes", json=dict(VALID_CHANGE_PAYLOAD, change_id="chg-e2e-dash"), headers=headers)

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert "ChangeGuard" in resp.text
    assert "chg-e2e-dash" in resp.text


def test_openapi_schema_is_served(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "ChangeGuard AI MultiCloud"


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
