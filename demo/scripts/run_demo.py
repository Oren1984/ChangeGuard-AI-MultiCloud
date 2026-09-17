#!/usr/bin/env python3
"""Runs all 15 ChangeGuard demo scenarios against a running instance.

Usage (from the repo root, with the stack up via `docker compose up -d`):

    docker compose exec app python demo/scripts/run_demo.py

Or against a locally-run instance:

    DEMO_BASE_URL=http://localhost:8000 python demo/scripts/run_demo.py

Uses only the standard library for HTTP so it can run inside the runtime
image without dev dependencies. The one exception is scenario 15 (tampered
audit-chain detection), which connects directly to PostgreSQL with
SQLAlchemy (already a runtime dependency) to simulate an attacker mutating
a historical record — something no legitimate API ever exposes.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

BASE_URL = os.environ.get("DEMO_BASE_URL", "http://localhost:8000").rstrip("/")
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

DEVELOPER = {"X-ChangeGuard-Actor": "dev.demo", "X-ChangeGuard-Role": "developer"}
ADMIN = {"X-ChangeGuard-Actor": "admin.demo", "X-ChangeGuard-Role": "admin"}
APPROVER = {"X-ChangeGuard-Actor": "approver.demo", "X-ChangeGuard-Role": "approver"}


def call(method: str, path: str, *, headers: dict | None = None, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url=f"{BASE_URL}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def banner(title: str) -> None:
    print(f"\n=== {title} ===")


def run_submit_and_evaluate(fixture_name: str) -> tuple[int, dict]:
    fixture = load_fixture(fixture_name)
    print(f"{fixture_name}: {fixture['description']}")
    status, body = call("POST", "/api/v1/changes", headers=DEVELOPER, body=fixture["payload"])
    change_id = fixture["payload"]["change_id"]
    status, body = call("POST", f"/api/v1/changes/{change_id}/evaluate", headers=DEVELOPER)
    if status >= 400:
        print(f"  -> HTTP {status}: {body.get('detail')} (already evaluated in a prior demo run?)")
    else:
        decision = (body.get("routing_decision") or {}).get("decision")
        print(f"  -> state={body.get('state')} decision={decision}")
    return status, body


def scenario_01_to_11() -> None:
    for i in range(1, 12):
        matches = sorted(FIXTURES_DIR.glob(f"{i:02d}_*.json"))
        if matches:
            banner(f"Scenario {i:02d}")
            run_submit_and_evaluate(matches[0].name)


def scenario_12_kill_switch() -> None:
    banner("Scenario 12: active kill switch blocks auto-clear")
    fixture = load_fixture("12_kill_switch_active.json")
    print(fixture["description"])

    call("POST", "/api/v1/admin/kill-switch/activate", headers=ADMIN, body={"reason": "demo"})
    status, body = call("POST", "/api/v1/changes", headers=DEVELOPER, body=fixture["payload"])
    change_id = fixture["payload"]["change_id"]
    status, body = call("POST", f"/api/v1/changes/{change_id}/evaluate", headers=DEVELOPER)
    if status >= 400:
        print(f"  -> HTTP {status}: {body.get('detail')} (already evaluated in a prior demo run?)")
    else:
        decision = (body.get("routing_decision") or {}).get("decision")
        print(f"  with kill switch ACTIVE   -> state={body.get('state')} decision={decision}")
    call("POST", "/api/v1/admin/kill-switch/deactivate", headers=ADMIN, body={"reason": "demo complete"})


def scenario_13_duplicate_webhook() -> None:
    banner("Scenario 13: duplicate webhook delivery is idempotent")
    fixture = load_fixture("13_duplicate_webhook.json")
    print(fixture["description"])
    provider = fixture["provider"]

    first_status, _ = call("POST", f"/api/v1/webhooks/{provider}", headers=DEVELOPER, body=fixture["payload"])
    second_status, _ = call("POST", f"/api/v1/webhooks/{provider}", headers=DEVELOPER, body=fixture["payload"])
    print(f"  first delivery status={first_status}, replay status={second_status}")
    assert second_status == 200, "replay should always return 200 (idempotent), regardless of prior demo runs"
    assert first_status in (200, 201), "unexpected status on first delivery"


def scenario_14_self_approval() -> None:
    banner("Scenario 14: submitter cannot approve their own change")
    fixture = load_fixture("14_self_approval_attempt.json")
    print(fixture["description"])
    change_id = fixture["payload"]["change_id"]

    call("POST", "/api/v1/changes", headers=DEVELOPER, body=fixture["payload"])
    call("POST", f"/api/v1/changes/{change_id}/evaluate", headers=DEVELOPER)

    self_approve_headers = {"X-ChangeGuard-Actor": DEVELOPER["X-ChangeGuard-Actor"], "X-ChangeGuard-Role": "approver"}
    status, body = call(
        "POST",
        f"/api/v1/changes/{change_id}/cab/approve",
        headers=self_approve_headers,
        body={"rationale": "self-approving (should be rejected)"},
    )
    print(f"  self-approval attempt -> HTTP {status}: {body.get('detail')}")
    assert status == 403, "separation-of-duties demo did not behave as expected"


def scenario_15_tampered_audit_chain() -> None:
    banner("Scenario 15: tampered audit-chain verification")
    print(
        "Demonstrates hash-chain tamper detection by mutating a historical "
        "audit record directly in PostgreSQL, inside a transaction that is "
        "rolled back afterwards so the persistent demo data is untouched."
    )
    database_url = os.environ.get(
        "CHANGEGUARD_DATABASE_URL", "postgresql+psycopg://changeguard:changeguard@db:5432/changeguard"
    )
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("  sqlalchemy not available in this environment; skipping direct-DB tamper demo.")
        return

    status, before = call("GET", "/api/v1/audit/verify")
    print(f"  before tampering -> is_valid={before['is_valid']} total_records={before['total_records']}")

    engine = create_engine(database_url, future=True)
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("UPDATE audit_records SET canonical_payload = :payload WHERE sequence = 1"),
                {"payload": '{"tampered":true}'},
            )

            from src.adapters.persistence.audit_repository_sqlalchemy import SqlAlchemyAuditRepository
            from sqlalchemy.orm import Session

            result = SqlAlchemyAuditRepository(Session(bind=conn)).verify_chain()
            print(f"  after tampering (uncommitted) -> is_valid={result.is_valid} reason={result.reason}")
            assert result.is_valid is False, "tamper-detection demo did not behave as expected"
            # Transaction rolls back automatically on context-manager exit below.
            raise _RollbackSentinel()


class _RollbackSentinel(Exception):
    pass


def main() -> None:
    banner("ChangeGuard AI MultiCloud — Demo Scenario Runner")
    print(f"Target: {BASE_URL}")

    scenario_01_to_11()
    scenario_12_kill_switch()
    scenario_13_duplicate_webhook()
    scenario_14_self_approval()
    try:
        scenario_15_tampered_audit_chain()
    except _RollbackSentinel:
        pass

    status, after = call("GET", "/api/v1/audit/verify")
    banner("Final audit-chain verification (should be valid again)")
    print(f"  is_valid={after['is_valid']} total_records={after['total_records']}")

    print("\nAll demo scenarios completed.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print(f"\nDEMO ASSERTION FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
