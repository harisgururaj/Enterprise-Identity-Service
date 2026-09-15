"""
Comprehensive Pytest Integration, Persistence, and Security Suite for Enterprise Identity Service Shift-Handover Workspace.
Verifies SQLite DB persistence across restarts, SHA-256 audit chain durability, /health and /health/ready endpoints,
fixture ingestion, HTTP 401/403 RBAC authorization, prototype demo identity context, impersonation prevention,
2-person dual user approvals, generic state snapshot rollbacks, SHA-256 audit hash chain tamper detection,
handover signoff validation, restricted admin endpoints, controlled benchmark reproducibility, resilience experiments,
and honest stakeholder validation.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app
from backend.database import SessionLocal, init_db
from backend.repository import seed_database_from_fixtures, get_workspace_state_db
from backend.models import FreshnessState, ActionStatus, ValidationCategory

client = TestClient(app)

SRE_HEADERS = {"X-User-Role": "SRE / On-Call Specialist", "X-User-Name": "Elena Rostova"}
IC_HEADERS = {"X-User-Role": "Incident Commander / Handover Lead", "X-User-Name": "Marcus Vance"}
DEV_HEADERS = {"X-User-Role": "Enterprise App Developer / Stakeholder", "X-User-Name": "Devon Zhao"}


def setup_function():
    """Reset workspace state with SRE authorization prior to each test."""
    client.post("/api/reset", headers=SRE_HEADERS)


def test_health_check_endpoint():
    """Verify /health endpoint returns HTTP 200 and UP status."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UP"
    assert "timestamp" in data


def test_health_readiness_endpoint():
    """Verify /health/ready endpoint performs SELECT 1 against SQLite DB and returns HTTP 200."""
    res = client.get("/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "READY"
    assert data["database"] == "CONNECTED"


def test_missing_role_header_returns_401_unauthorized():
    """Verify missing X-User-Role header returns HTTP 401 Unauthorized (never defaults to SRE)."""
    res = client.post("/api/hypotheses", headers={"X-User-Name": "Elena"}, json={"title": "Test", "description": "Test"})
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]


def test_missing_username_header_returns_401_unauthorized():
    """Verify missing X-User-Name header returns HTTP 401 Unauthorized."""
    res = client.post("/api/hypotheses", headers={"X-User-Role": "SRE / On-Call Specialist"}, json={"title": "Test", "description": "Test"})
    assert res.status_code == 401
    assert "Unauthorized" in res.json()["detail"]


def test_invalid_role_header_returns_403_forbidden():
    """Verify invalid X-User-Role header returns HTTP 403 Forbidden."""
    res = client.post(
        "/api/hypotheses",
        headers={"X-User-Role": "SuperAdminFakeRole", "X-User-Name": "Elena"},
        json={"title": "Test", "description": "Test"}
    )
    assert res.status_code == 403


def test_body_actor_impersonation_ignored():
    """Verify passing fake actor string in JSON body does NOT impersonate; audit records header username."""
    res = client.post(
        "/api/hypotheses",
        headers=SRE_HEADERS,
        json={
            "title": "Impersonation Test",
            "description": "Test",
            "created_by": "Fake User Impersonator"
        }
    )
    assert res.status_code == 200
    assert res.json()["hypothesis"]["created_by"] == "Elena Rostova"


def test_stakeholder_role_forbidden_actions():
    """Verify Developer/Stakeholder role receives HTTP 403 on operational mutation endpoints."""
    exec_res = client.post("/api/actions/execute", headers=DEV_HEADERS, json={"action_id": "ACT-1003"})
    assert exec_res.status_code == 403

    rb_res = client.post("/api/actions/rollback", headers=DEV_HEADERS, json={"action_id": "ACT-1001", "rationale": "Forbidden Test"})
    assert rb_res.status_code == 403

    appr_res = client.post("/api/change-review/approve", headers=DEV_HEADERS, json={"action_id": "ACT-1003"})
    assert appr_res.status_code == 403

    toggle_res = client.post("/api/data-sources/toggle", headers=DEV_HEADERS, json={"source_name": "chat_excerpts", "state": "MISSING"})
    assert toggle_res.status_code == 403


def test_explicit_five_data_sources_toggling():
    """Verify each of 5 data sources can be toggled using explicit source map in SQLite DB."""
    sources = ["incident_notes", "chat_excerpts", "dashboards", "ownership_changes", "action_logs"]
    for src in sources:
        res = client.post(
            "/api/data-sources/toggle",
            headers=SRE_HEADERS,
            json={"source_name": src, "state": "MISSING"}
        )
        assert res.status_code == 200
        assert res.json()["freshness"][src] == "MISSING"


def test_fixture_reingestion_endpoint():
    """Verify /api/fixtures/ingest endpoint re-ingests 5 synthetic JSON enterprise fixtures."""
    res = client.post("/api/fixtures/ingest", headers=SRE_HEADERS)
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCESS"


def test_two_person_dual_approval_and_same_user_rejection():
    """Verify 2-person dual approval state machine and same-user rejection."""
    a1 = client.post("/api/change-review/approve", headers=IC_HEADERS, json={"action_id": "ACT-1003"})
    assert a1.status_code == 200
    assert a1.json()["change_review"]["status"] == "PENDING_APPROVAL_2"

    a_same = client.post("/api/change-review/approve", headers=IC_HEADERS, json={"action_id": "ACT-1003"})
    assert a_same.status_code == 400
    assert "Dual Approval Failure" in a_same.json()["detail"]

    a2 = client.post("/api/change-review/approve", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})
    assert a2.status_code == 200
    assert a2.json()["change_review"]["status"] == "APPROVED"


def test_execution_blocked_without_approval_and_allowed_after_approval():
    """Verify unapproved high-impact action execution fails, and succeeds after 2-person approval."""
    exec_blocked = client.post("/api/actions/execute", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})
    assert exec_blocked.status_code == 403

    client.post("/api/change-review/approve", headers=IC_HEADERS, json={"action_id": "ACT-1003"})
    client.post("/api/change-review/approve", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})

    exec_allowed = client.post("/api/actions/execute", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})
    assert exec_allowed.status_code == 200
    assert exec_allowed.json()["action"]["status"] == "EXECUTED"


def test_generic_state_rollback_and_double_rollback_rejection():
    """Verify snapshot rollback restores before_state values and rejects double rollback in SQLite DB."""
    client.post("/api/change-review/approve", headers=IC_HEADERS, json={"action_id": "ACT-1003"})
    client.post("/api/change-review/approve", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})
    client.post("/api/actions/execute", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})

    rb_res = client.post("/api/actions/rollback", headers=SRE_HEADERS, json={"action_id": "ACT-1003", "rationale": "State restoration test"})
    assert rb_res.status_code == 200
    assert rb_res.json()["action"]["status"] == "ROLLED_BACK"

    ws = client.get("/api/workspace", headers=SRE_HEADERS).json()
    err_metric = next(m for m in ws["raw_data_sources"]["dashboard_metrics"] if m["id"] == "METRIC-AUTH-02")
    assert err_metric["current_value"] == 18.6

    rb_double = client.post("/api/actions/rollback", headers=SRE_HEADERS, json={"action_id": "ACT-1003"})
    assert rb_double.status_code == 400
    assert "already been rolled back" in rb_double.json()["detail"]


def test_rollback_before_execution_rejection():
    """Verify rollback attempt on unexecuted action fails with HTTP 400."""
    rb_res = client.post("/api/actions/rollback", headers=SRE_HEADERS, json={"action_id": "ACT-1004"})
    assert rb_res.status_code == 400
    assert "has not been executed yet" in rb_res.json()["detail"]


def test_sha256_audit_trail_verification_and_tamper_detection():
    """Verify SHA-256 hash chain validity and automated tamper detection in SQLite DB."""
    v1 = client.get("/api/audit/verify", headers=SRE_HEADERS).json()
    assert v1["valid"] is True
    assert v1["first_invalid_record"] is None

    client.post("/api/audit/tamper-test", headers=SRE_HEADERS, json={"record_index": 0})

    v2 = client.get("/api/audit/verify", headers=SRE_HEADERS).json()
    assert v2["valid"] is False
    assert v2["first_invalid_record"] == "AUD-5001"


def test_sqlite_persistence_across_db_sessions():
    """Verify created hypothesis persists durably in SQLite database across separate DB sessions."""
    res = client.post(
        "/api/hypotheses",
        headers=SRE_HEADERS,
        json={"title": "Persistent DB Hypothesis Test", "description": "Testing SQLite DB persistence"}
    )
    assert res.status_code == 200
    hypo_id = res.json()["hypothesis"]["id"]

    db = SessionLocal()
    ws = get_workspace_state_db(db)
    db.close()

    found = any(h.id == hypo_id for h in ws.hypotheses)
    assert found is True


def test_handover_signoff_validation():
    """Verify handover signoff requires non-empty and distinct outgoing/incoming identities."""
    res_empty = client.post("/api/handover/signoff", headers=IC_HEADERS, json={"outgoing_user": " ", "incoming_user": "Elena"})
    assert res_empty.status_code == 400

    res_same = client.post("/api/handover/signoff", headers=IC_HEADERS, json={"outgoing_user": "Marcus Vance", "incoming_user": "marcus vance"})
    assert res_same.status_code == 400

    res_ok = client.post("/api/handover/signoff", headers=IC_HEADERS, json={"outgoing_user": "Marcus Vance", "incoming_user": "Elena Rostova"})
    assert res_ok.status_code == 200
    assert res_ok.json()["handover_status"] == "ACCEPTED"


def test_reset_endpoint_requires_authorization():
    """Verify /api/reset returns 401 without role header and 403 for stakeholder role."""
    assert client.post("/api/reset").status_code == 401
    assert client.post("/api/reset", headers=DEV_HEADERS).status_code == 403
    assert client.post("/api/reset", headers=SRE_HEADERS).status_code == 200


def test_stakeholder_validation_honesty_default_not_tested():
    """Verify default stakeholder validation state is NOT_TESTED and summary only counts observed data."""
    res = client.get("/api/stakeholder-validation", headers=SRE_HEADERS).json()
    summary = res["summary"]
    assert summary["not_tested_count"] == 8
    assert summary["observed_validation_count"] == 0
    assert summary["observed_completion_rate_percent"] == 0.0

    client.post(
        "/api/stakeholder-validation",
        headers=DEV_HEADERS,
        json={
            "task_id": "TASK-01",
            "completed": True,
            "completion_time_sec": 14.5,
            "error_count": 0,
            "comments": "Observed real user test",
            "validation_status": "OBSERVED_VALIDATION"
        }
    )

    res_after = client.get("/api/stakeholder-validation", headers=SRE_HEADERS).json()
    summary_after = res_after["summary"]
    assert summary_after["observed_validation_count"] == 1
    assert summary_after["observed_completion_rate_percent"] == 12.5


def test_controlled_benchmark_and_resilience_reproducibility():
    """Verify benchmark and resilience experiment calculations are reproducible with fixed seed."""
    b1 = client.get("/api/benchmark?trials=100&seed=42", headers=SRE_HEADERS).json()
    b2 = client.get("/api/benchmark?trials=100&seed=42", headers=SRE_HEADERS).json()
    assert b1["solution_handover_delay_minutes"] == b2["solution_handover_delay_minutes"]
    assert b1["pass_target_evaluation"] is True

    r1 = client.get("/api/resilience-experiment?trials=100&seed=42", headers=SRE_HEADERS).json()
    r2 = client.get("/api/resilience-experiment?trials=100&seed=42", headers=SRE_HEADERS).json()
    assert r1["conditions"][0]["mean_recovery_delay_minutes"] == r2["conditions"][0]["mean_recovery_delay_minutes"]
    assert len(r1["conditions"]) == 8
