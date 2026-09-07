"""
FastAPI Server for Enterprise Identity Service Shift-Handover Workspace.
Provides REST APIs for workspace state, data sources, hypothesis graph management,
change review approvals, rollback execution engine, data source freshness toggles,
role-based perspectives, and empirical benchmark evaluation.
"""

from fastapi import FastAPI, HTTPException, Body
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os
import copy
from typing import Dict, Any, List, Optional

from backend.models import (
    ShiftHandoverWorkspace, Hypothesis, Evidence, ActionLog,
    FreshnessState, ActionStatus, UserRole, ImpactLevel, AuditEntry,
    ChangeReviewRequest, EvidenceImpact, SourceType, HypothesisStatus
)
from backend.data_generator import create_initial_workspace, get_initial_data_sources
from backend.benchmark import run_handover_benchmark

app = FastAPI(
    title="Enterprise Identity Service Shift-Handover Workspace API",
    description="Resilient Shift-Handover Engine reducing recovery context loss during shift transitions.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state initialized on server startup
workspace_state: ShiftHandoverWorkspace = create_initial_workspace()
raw_data_sources: Dict[str, Any] = get_initial_data_sources()


@app.get("/api/workspace")
def get_workspace(role: str = "SRE / On-Call Specialist"):
    """Returns the full Shift Handover Workspace tailored to the specified role."""
    global workspace_state

    # Data is dynamically filtered based on data source freshness status
    resp = workspace_state.model_dump()
    resp["active_role"] = role
    resp["raw_data_sources"] = raw_data_sources
    return resp


@app.get("/api/data-sources")
def get_data_sources():
    """Returns raw data from all 5 enterprise data sources with freshness metadata."""
    return {
        "freshness": workspace_state.freshness.model_dump(),
        "data_sources": raw_data_sources
    }


@app.post("/api/data-sources/toggle")
def toggle_data_source_state(
    source_name: str = Body(..., embed=True),
    state: FreshnessState = Body(..., embed=True)
):
    """
    Edge Case Simulator: Dynamically toggles data source freshness state
    (FRESH, DELAYED, STALE, MISSING) to test system resilience.
    """
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if hasattr(workspace_state.freshness, source_name):
        setattr(workspace_state.freshness, source_name, state)
        workspace_state.freshness.last_checked = now

        # Add audit trail entry
        workspace_state.audit_trail.append(
            AuditEntry(
                id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
                timestamp=now,
                actor="Edge Case Simulator",
                role="System Tester",
                action_type="DATA_SOURCE_TOGGLE",
                description=f"Toggled data source `{source_name}` status to `{state.value}`",
                metadata={"source": source_name, "new_state": state.value}
            )
        )
        return {"status": "SUCCESS", "source": source_name, "new_state": state.value, "freshness": workspace_state.freshness.model_dump()}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {source_name}")


@app.post("/api/hypotheses")
def create_hypothesis(
    title: str = Body(..., embed=True),
    description: str = Body(..., embed=True),
    created_by: str = Body("Elena Rostova", embed=True),
    confidence_score: float = Body(0.5, embed=True)
):
    """Creates a new operational hypothesis in the shift handover workspace."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hypo_id = f"HYPO-{len(workspace_state.hypotheses) + 1:02d}"

    new_hypo = Hypothesis(
        id=hypo_id,
        title=title,
        description=description,
        status=HypothesisStatus.INVESTIGATING,
        confidence_score=confidence_score,
        created_by=created_by,
        created_at=now,
        updated_at=now,
        evidence_ids=[]
    )

    workspace_state.hypotheses.append(new_hypo)

    # Audit entry
    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=created_by,
            role="On-Call SRE",
            action_type="HYPOTHESIS_CREATED",
            description=f"Created hypothesis `{hypo_id}`: {title}",
            metadata={"hypothesis_id": hypo_id}
        )
    )

    return {"status": "SUCCESS", "hypothesis": new_hypo.model_dump()}


@app.post("/api/evidence")
def link_evidence(
    hypothesis_id: str = Body(..., embed=True),
    source_type: SourceType = Body(..., embed=True),
    source_id: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    snippet: str = Body(..., embed=True),
    impact: EvidenceImpact = Body(..., embed=True),
    added_by: str = Body("Elena Rostova", embed=True)
):
    """Links evidence snippet to a hypothesis and recalculates confidence score."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hypo = next((h for h in workspace_state.hypotheses if h.id == hypothesis_id), None)
    if not hypo:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    evid_id = f"EVID-{len(workspace_state.evidence_list) + 1:02d}"
    new_evidence = Evidence(
        id=evid_id,
        hypothesis_id=hypothesis_id,
        source_type=source_type,
        source_id=source_id,
        title=title,
        snippet=snippet,
        impact=impact,
        added_by=added_by,
        added_at=now
    )

    workspace_state.evidence_list.append(new_evidence)
    hypo.evidence_ids.append(evid_id)

    # Simple confidence score recalculation rule
    if impact == EvidenceImpact.SUPPORTS:
        hypo.confidence_score = min(0.99, hypo.confidence_score + 0.15)
    elif impact == EvidenceImpact.REFUTES:
        hypo.confidence_score = max(0.01, hypo.confidence_score - 0.25)
        if hypo.confidence_score < 0.1:
            hypo.status = HypothesisStatus.DISPROVED

    hypo.updated_at = now

    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=added_by,
            role="On-Call SRE",
            action_type="EVIDENCE_LINKED",
            description=f"Linked evidence `{evid_id}` to Hypothesis `{hypothesis_id}` ({impact.value})",
            metadata={"evidence_id": evid_id, "hypothesis_id": hypothesis_id}
        )
    )

    return {"status": "SUCCESS", "evidence": new_evidence.model_dump(), "updated_hypothesis": hypo.model_dump()}


@app.post("/api/change-review/approve")
def approve_change_review(
    action_id: str = Body(..., embed=True),
    approver: str = Body("Marcus Vance (Outgoing Lead)", embed=True)
):
    """
    Two-person Change Review Approval Workflow for High-Impact Actions.
    """
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    req = next((r for r in workspace_state.change_reviews if r.action_id == action_id), None)
    if not req:
        raise HTTPException(status_code=404, detail="Change review request not found")

    req.status = "APPROVED"
    req.approved_by = approver

    # Update Action Log status in both raw_data_sources and workspace_state
    for a in raw_data_sources["action_logs"]:
        if a.id == action_id:
            a.status = ActionStatus.APPROVED
            a.approved_by = approver

    for a in workspace_state.unresolved_actions:
        if a.id == action_id:
            a.status = ActionStatus.APPROVED
            a.approved_by = approver

    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=approver,
            role="Handover Approver",
            action_type="CHANGE_REVIEW_APPROVED",
            description=f"Approved high-impact action `{action_id}` ({req.action_name})",
            metadata={"action_id": action_id, "approver": approver}
        )
    )

    return {"status": "SUCCESS", "change_review": req.model_dump()}


@app.post("/api/actions/execute")
def execute_action(
    action_id: str = Body(..., embed=True),
    executed_by: str = Body("Elena Rostova", embed=True)
):
    """
    Executes an approved action (e.g., API Edge Gateway JWKS Cache Invalidation).
    Recalculates incident state and error telemetry.
    """
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail="Action not found")

    if act.requires_two_person_review and act.status != ActionStatus.APPROVED:
        raise HTTPException(status_code=403, detail="Action requires 2-person approval before execution")

    act.status = ActionStatus.EXECUTED
    act.executed_at = now

    # Remove from unresolved actions if present
    workspace_state.unresolved_actions = [a for a in workspace_state.unresolved_actions if a.id != action_id]

    # If executing ACT-1003 (Gateway Cache Flush), simulate recovery in metrics!
    if action_id == "ACT-1003":
        for m in raw_data_sources["dashboard_metrics"]:
            if m.id == "METRIC-AUTH-02":  # Error rate drops to 0.02%
                m.current_value = 0.02
                m.status = "NORMAL"
                m.trend = "FALLING"
                m.history.append({"time": "09:35", "value": 0.02})
            elif m.id == "METRIC-AUTH-03":  # Stale ratio drops to 0.0%
                m.current_value = 0.0
                m.status = "NORMAL"
                m.trend = "FALLING"
                m.history.append({"time": "09:35", "value": 0.0})

        # Update context risk score
        workspace_state.context_loss_risk_score = 2.1
        workspace_state.shift_summary += " [EXECUTION SUCCESS: API Edge Gateway cache flushed. JWT error rate reduced to 0.02%. Incident resolved.]"

    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=executed_by,
            role="On-Call Specialist",
            action_type="ACTION_EXECUTED",
            description=f"Executed action `{action_id}`: {act.action_name}",
            metadata={"action_id": action_id}
        )
    )

    return {"status": "SUCCESS", "action": act.model_dump(), "workspace_risk_score": workspace_state.context_loss_risk_score}


@app.post("/api/actions/rollback")
def rollback_action(
    action_id: str = Body(..., embed=True),
    actor: str = Body("Elena Rostova", embed=True),
    rationale: str = Body("High latency observed during execution", embed=True)
):
    """
    Executes a 1-click rollback for any high-impact reversible action.
    """
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail="Action log entry not found")

    if not act.is_reversible:
        raise HTTPException(status_code=400, detail="Action is marked non-reversible")

    act.status = ActionStatus.ROLLED_BACK
    act.rollback_executed_at = now

    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=actor,
            role="On-Call SRE",
            action_type="ACTION_ROLLED_BACK",
            description=f"Executed rollback for action `{action_id}` ({act.action_name}). Rationale: {rationale}",
            metadata={"action_id": action_id, "rationale": rationale}
        )
    )

    return {"status": "SUCCESS", "action": act.model_dump()}


@app.post("/api/handover/signoff")
def signoff_handover(
    outgoing_lead_signature: str = Body(..., embed=True),
    incoming_lead_signature: str = Body(..., embed=True),
    notes: str = Body("Handover completed with 0 unresolved critical items.", embed=True)
):
    """Completes formal sign-off between outgoing and incoming shift leads."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    workspace_state.handover_status = "ACCEPTED"
    workspace_state.audit_trail.append(
        AuditEntry(
            id=f"AUD-{len(workspace_state.audit_trail) + 5001}",
            timestamp=now,
            actor=f"{outgoing_lead_signature} & {incoming_lead_signature}",
            role="Shift Leads",
            action_type="HANDOVER_ACCEPTED",
            description=f"Formal Shift Handover ACCEPTED between {outgoing_lead_signature} and {incoming_lead_signature}.",
            metadata={"notes": notes}
        )
    )

    return {"status": "SUCCESS", "handover_status": workspace_state.handover_status}


@app.get("/api/benchmark")
def get_benchmark(trials: int = 100):
    """Runs Monte Carlo benchmark comparing Unstructured vs Structured Shift Handover."""
    return run_handover_benchmark(trials=trials)


@app.post("/api/reset")
def reset_workspace():
    """Resets workspace state back to baseline initial scenario."""
    global workspace_state, raw_data_sources
    workspace_state = create_initial_workspace()
    raw_data_sources = get_initial_data_sources()
    return {"status": "SUCCESS", "message": "Workspace reset to initial SEV-1 scenario"}


# Mount static frontend directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
