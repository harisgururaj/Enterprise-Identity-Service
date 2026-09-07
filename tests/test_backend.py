"""
Comprehensive Unit and Integration Test Suite for Enterprise Identity Service Shift-Handover Workspace.
Verifies Server-Side RBAC, Hash-Chained Audit Verification, Tamper Detection, Two-Person Dual Approvals,
Real State Snapshot Rollbacks, Invalid Evidence Source Validation, Controlled Benchmarks, and Resilience Experiments.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app, workspace_state, raw_data_sources
from backend.models import FreshnessState, ActionStatus, EvidenceImpact, SourceType


client = TestClient(app)


def setup_function():
    """Reset workspace state before each test."""
    client.post("/api/reset")


def test_get_workspace():
    """Verify workspace fetch returns incident details, freshness status, and resilience panel."""
    res = client.get("/api/workspace", headers={"X-User-Role": "SRE / On-Call Specialist"})
    assert res.status_code == 200
    data = res.json()
    assert data["incident_id"] == "INC-9042"
    assert data["severity"] == "SEV-1"
    assert len(data["hypotheses"]) >= 3
    assert len(data["evidence_list"]) >= 4
    assert len(data["source_resilience"]) == 5
    assert "freshness" in data


def test_rbac_server_side_authorization():
    """Verify server-side RBAC rejects unauthorized requests with HTTP 403 Forbidden."""
    # 1. Stakeholder role attempting to execute action -> 403 Forbidden
    res_exec = client.post(
        "/api/actions/execute",
        headers={"X-User-Role": "Enterprise App Developer / Stakeholder"},
        json={"action_id": "ACT-1003", "executed_by": "Stakeholder User"}
    )
    assert res_exec.status_code == 403
    assert "Forbidden" in res_exec.json()["detail"]

    # 2. Stakeholder role attempting rollback -> 403 Forbidden
    res_rb = client.post(
        "/api/actions/rollback",
        headers={"X-User-Role": "Enterprise App Developer / Stakeholder"},
        json={"action_id": "ACT-1001", "actor": "Stakeholder User", "rationale": "Test"}
    )
    assert res_rb.status_code == 403

    # 3. Stakeholder role attempting change review approval -> 403 Forbidden
    res_appr = client.post(
        "/api/change-review/approve",
        headers={"X-User-Role": "Enterprise App Developer / Stakeholder"},
        json={"action_id": "ACT-1003", "approver": "Stakeholder User"}
    )
    assert res_appr.status_code == 403


def test_sha256_hash_chained_audit_trail_and_tampering_detection():
    """Verify SHA-256 audit chain integrity and tamper detection endpoint."""
    # 1. Initial audit trail should be 100% valid
    res_v1 = client.get("/api/audit/verify")
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["valid"] is True
    assert data_v1["records_checked"] >= 3
    assert data_v1["first_invalid_record"] is None

    # 2. Simulate audit record tampering
    t_res = client.post("/api/audit/tamper-test", json={"record_index": 0})
    assert t_res.status_code == 200

    # 3. Audit verification must now return valid=False
    res_v2 = client.get("/api/audit/verify")
    assert res_v2.status_code == 200
    data_v2 = res_v2.json()
    assert data_v2["valid"] is False
    assert data_v2["first_invalid_record"] == "AUD-5001"


def test_two_person_dual_approval_and_same_user_rejection():
    """Verify 2-person change review approval workflow and same-user rejection."""
    # 1. First approval by Marcus Vance (Shift Alpha)
    appr1 = client.post(
        "/api/change-review/approve",
        headers={"X-User-Role": "Incident Commander / Handover Lead"},
        json={"action_id": "ACT-1003", "approver": "Marcus Vance"}
    )
    assert appr1.status_code == 200
    assert appr1.json()["change_review"]["status"] == "PENDING_APPROVAL_2"

    # 2. Re-approval by SAME user Marcus Vance must fail (400)
    appr_same = client.post(
        "/api/change-review/approve",
        headers={"X-User-Role": "Incident Commander / Handover Lead"},
        json={"action_id": "ACT-1003", "approver": "Marcus Vance"}
    )
    assert appr_same.status_code == 400
    assert "Dual Approval Failure" in appr_same.json()["detail"]

    # 3. Second approval by DISTINCT user Elena Rostova (Shift Beta)
    appr2 = client.post(
        "/api/change-review/approve",
        headers={"X-User-Role": "Incident Commander / Handover Lead"},
        json={"action_id": "ACT-1003", "approver": "Elena Rostova"}
    )
    assert appr2.status_code == 200
    assert appr2.json()["change_review"]["status"] == "APPROVED"


def test_action_execution_and_real_state_rollback():
    """Verify state snapshot capture during execution and physical state restoration on rollback."""
    # 1. Complete 2-person approval for ACT-1003
    client.post("/api/change-review/approve", headers={"X-User-Role": "Incident Commander / Handover Lead"}, json={"action_id": "ACT-1003", "approver": "Marcus Vance"})
    client.post("/api/change-review/approve", headers={"X-User-Role": "Incident Commander / Handover Lead"}, json={"action_id": "ACT-1003", "approver": "Elena Rostova"})

    # 2. Execute action ACT-1003
    exec_res = client.post(
        "/api/actions/execute",
        headers={"X-User-Role": "SRE / On-Call Specialist"},
        json={"action_id": "ACT-1003", "executed_by": "Elena Rostova"}
    )
    assert exec_res.status_code == 200
    act_data = exec_res.json()["action"]
    assert act_data["status"] == "EXECUTED"
    assert act_data["before_state"]["jwt_error_rate_percent"] == 18.6
    assert act_data["after_state"]["jwt_error_rate_percent"] == 0.02

    # Verify metrics updated to 0.02%
    ws = client.get("/api/workspace").json()
    err_metric = next(m for m in ws["raw_data_sources"]["dashboard_metrics"] if m["id"] == "METRIC-AUTH-02")
    assert err_metric["current_value"] == 0.02

    # 3. Trigger 1-Click Rollback for ACT-1003
    rb_res = client.post(
        "/api/actions/rollback",
        headers={"X-User-Role": "SRE / On-Call Specialist"},
        json={"action_id": "ACT-1003", "actor": "Elena Rostova", "rationale": "Test state restoration"}
    )
    assert rb_res.status_code == 200
    rb_data = rb_res.json()["action"]
    assert rb_data["status"] == "ROLLED_BACK"

    # Verify metrics physically restored to 18.6%
    ws_after_rb = client.get("/api/workspace").json()
    err_metric_restored = next(m for m in ws_after_rb["raw_data_sources"]["dashboard_metrics"] if m["id"] == "METRIC-AUTH-02")
    assert err_metric_restored["current_value"] == 18.6


def test_invalid_evidence_source_id_rejection():
    """Verify evidence linking fails with HTTP 404 if source_id does not exist."""
    res = client.post(
        "/api/evidence",
        headers={"X-User-Role": "SRE / On-Call Specialist"},
        json={
            "hypothesis_id": "HYPO-01",
            "source_type": "CHAT",
            "source_id": "NON_EXISTENT_SOURCE_ID_999",
            "title": "Fake evidence title",
            "snippet": "Fake snippet",
            "impact": "SUPPORTS",
            "added_by": "Tester"
        }
    )
    assert res.status_code == 404
    assert "Invalid Source ID" in res.json()["detail"]


def test_controlled_benchmark_and_resilience_experiments():
    """Verify benchmark engine reproducibility, target comparison, and resilience experiment."""
    # 1. Benchmark API
    bench_res = client.get("/api/benchmark?trials=100&seed=42")
    assert bench_res.status_code == 200
    data = bench_res.json()
    assert data["pass_target_evaluation"] is True
    assert data["percentage_reduction"] >= 25.0
    assert "95% CI" in data["confidence_interval_95"]

    # 2. Resilience Experiment API
    resil_res = client.get("/api/resilience-experiment")
    assert resil_res.status_code == 200
    conditions = resil_res.json()
    assert len(conditions) == 4
    assert conditions[0]["status"] == "OPERATIONAL"


def test_stakeholder_validation_workflow():
    """Verify observational stakeholder validation workflow API endpoints."""
    # 1. Get initial tasks
    get_res = client.get("/api/stakeholder-validation")
    assert get_res.status_code == 200
    summary = get_res.json()["summary"]
    assert summary["total_tasks"] == 8
    assert summary["task_completion_rate_percent"] == 100.0

    # 2. Record validation task
    rec_res = client.post(
        "/api/stakeholder-validation",
        json={
            "task_id": "TASK-01",
            "completed": True,
            "completion_time_sec": 11.2,
            "error_count": 0,
            "comments": "Observed fast identification of SEV-1 banner",
            "user_role": "Enterprise App Developer / Stakeholder"
        }
    )
    assert rec_res.status_code == 200
    assert rec_res.json()["task"]["completion_time_sec"] == 11.2
