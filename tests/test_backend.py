"""
Unit and Integration Tests for Enterprise Identity Service Shift-Handover Workspace.
Verifies API endpoints, hypothesis confidence updates, edge case toggles,
two-person review approvals, 1-click rollbacks, and empirical benchmark execution.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app import app, workspace_state, raw_data_sources
from backend.models import FreshnessState, ActionStatus, EvidenceImpact, SourceType


client = TestClient(app)


def test_get_workspace():
    """Verify workspace fetch API returns correct initial SEV-1 incident details."""
    response = client.get("/api/workspace?role=SRE%20%2F%20On-Call%20Specialist")
    assert response.status_code == 200
    data = response.json()
    assert data["incident_id"] == "INC-9042"
    assert data["severity"] == "SEV-1"
    assert len(data["hypotheses"]) >= 3
    assert len(data["evidence_list"]) >= 4
    assert "freshness" in data


def test_data_sources_freshness_toggle():
    """Verify Edge Case Simulator can set data sources to MISSING or DELAYED."""
    response = client.post(
        "/api/data-sources/toggle",
        json={"source_name": "chat_excerpts", "state": "MISSING"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "chat_excerpts"
    assert data["new_state"] == "MISSING"

    # Fetch workspace and verify freshness badge updated
    ws = client.get("/api/workspace").json()
    assert ws["freshness"]["chat_excerpts"] == "MISSING"

    # Reset data source back to FRESH
    client.post(
        "/api/data-sources/toggle",
        json={"source_name": "chat_excerpts", "state": "FRESH"}
    )


def test_create_hypothesis_and_link_evidence():
    """Verify creating hypothesis and linking supporting evidence updates confidence score."""
    # 1. Create Hypothesis
    hypo_res = client.post(
        "/api/hypotheses",
        json={
            "title": "Gateway Network Interface MTU Mismatch",
            "description": "Test hypothesis regarding MTU sizing across edge nodes",
            "created_by": "Test Engineer",
            "confidence_score": 0.40
        }
    )
    assert hypo_res.status_code == 200
    hypo_id = hypo_res.json()["hypothesis"]["id"]

    # 2. Link Supporting Evidence
    evid_res = client.post(
        "/api/evidence",
        json={
            "hypothesis_id": hypo_id,
            "source_type": "CHAT",
            "source_id": "CHAT-8801",
            "title": "Packet drops logged on eth0",
            "snippet": "Packet dropped logs on edge nodes",
            "impact": "SUPPORTS",
            "added_by": "Test Engineer"
        }
    )
    assert evid_res.status_code == 200
    updated_hypo = evid_res.json()["updated_hypothesis"]
    assert updated_hypo["confidence_score"] > 0.40


def test_two_person_change_review_and_execution():
    """Verify high-impact action requires approval before execution, and updates metrics on execute."""
    # Reset workspace first
    client.post("/api/reset")

    # Attempt execution of unapproved ACT-1003 (requires 2-person review)
    exec_fail = client.post(
        "/api/actions/execute",
        json={"action_id": "ACT-1003", "executed_by": "Elena Rostova"}
    )
    assert exec_fail.status_code == 403

    # Approve action ACT-1003
    appr_res = client.post(
        "/api/change-review/approve",
        json={"action_id": "ACT-1003", "approver": "Marcus Vance"}
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["change_review"]["status"] == "APPROVED"

    # Now execute ACT-1003
    exec_success = client.post(
        "/api/actions/execute",
        json={"action_id": "ACT-1003", "executed_by": "Elena Rostova"}
    )
    assert exec_success.status_code == 200
    assert exec_success.json()["action"]["status"] == "EXECUTED"
    assert exec_success.json()["workspace_risk_score"] < 5.0


def test_rollback_action():
    """Verify 1-click rollback of reversible action logs audit entry and updates status."""
    rb_res = client.post(
        "/api/actions/rollback",
        json={
            "action_id": "ACT-1001",
            "actor": "Elena Rostova",
            "rationale": "Rollback Key Rotation to v3.9"
        }
    )
    assert rb_res.status_code == 200
    assert rb_res.json()["action"]["status"] == "ROLLED_BACK"


def test_benchmark_simulation():
    """Verify benchmark endpoint computes valid recovery delay reduction metrics."""
    bench_res = client.get("/api/benchmark?trials=50")
    assert bench_res.status_code == 200
    data = bench_res.json()
    assert data["percentage_reduction"] > 50.0
    assert data["solution_handover_delay_minutes"] < data["baseline_handover_delay_minutes"]
    assert "error_analysis" in data
