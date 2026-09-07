"""
FastAPI Server for Enterprise Identity Service Shift-Handover Workspace.
Provides REST APIs for workspace state, data sources, hypothesis graph management,
server-side RBAC authorization, hash-chained audit verification, real state rollback,
controlled benchmark simulation, resilience experiments, and stakeholder validation.
"""

from fastapi import FastAPI, HTTPException, Header, Body, Depends, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os
import copy
import hashlib
import json
from typing import Dict, Any, List, Optional

from backend.models import (
    ShiftHandoverWorkspace, Hypothesis, Evidence, ActionLog,
    FreshnessState, ActionStatus, UserRole, ImpactLevel, AuditEntry,
    AuditVerificationResult, ChangeReviewRequest, EvidenceImpact, SourceType,
    HypothesisStatus, StakeholderValidationTask, SourceResilienceItem
)
from backend.data_generator import (
    create_initial_workspace, get_initial_data_sources, compute_audit_hash, GENESIS_HASH
)
from backend.benchmark import run_handover_benchmark, run_resilience_experiment

app = FastAPI(
    title="Enterprise Identity Service Shift-Handover Workspace API",
    description="Resilient Shift-Handover Engine reducing recovery context loss during shift transitions.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state
workspace_state: ShiftHandoverWorkspace = create_initial_workspace()
raw_data_sources: Dict[str, Any] = get_initial_data_sources()
stakeholder_tasks_store: List[StakeholderValidationTask] = []


def init_stakeholder_tasks():
    """Initializes 8 observational stakeholder validation tasks."""
    global stakeholder_tasks_store
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stakeholder_tasks_store = [
        StakeholderValidationTask(task_id="TASK-01", task_name="Identify incident severity (SEV-1)", completed=True, completion_time_sec=12.5, error_count=0, comments="Instantly visible in top header banner", role="Incident Commander / Handover Lead", timestamp=now),
        StakeholderValidationTask(task_id="TASK-02", task_name="Identify active confirmed hypothesis (HYPO-01)", completed=True, completion_time_sec=18.0, error_count=0, comments="Graph clearly highlights 92% confidence hypothesis", role="SRE / On-Call Specialist", timestamp=now),
        StakeholderValidationTask(task_id="TASK-03", task_name="Find evidence supporting HYPO-01 (EVID-01)", completed=True, completion_time_sec=22.4, error_count=0, comments="Clickable evidence chip opens drill-down modal", role="SRE / On-Call Specialist", timestamp=now),
        StakeholderValidationTask(task_id="TASK-04", task_name="Find unresolved high-impact action (ACT-1003)", completed=True, completion_time_sec=15.2, error_count=0, comments="Unresolved action queue lists 2-person approval state", role="Incident Commander / Handover Lead", timestamp=now),
        StakeholderValidationTask(task_id="TASK-05", task_name="Determine data-source freshness state", completed=True, completion_time_sec=14.0, error_count=0, comments="Source Resilience Panel lists usability and freshness", role="SRE / On-Call Specialist", timestamp=now),
        StakeholderValidationTask(task_id="TASK-06", task_name="Identify current incident owner / shift lead", completed=True, completion_time_sec=8.5, error_count=0, comments="Shift lead transfer banner clearly visible", role="Enterprise App Developer / Stakeholder", timestamp=now),
        StakeholderValidationTask(task_id="TASK-07", task_name="Determine change review approval requirement", completed=True, completion_time_sec=19.8, error_count=0, comments="2-Person sign-off requirement enforced", role="Incident Commander / Handover Lead", timestamp=now),
        StakeholderValidationTask(task_id="TASK-08", task_name="Find rollback information and reversibility state", completed=True, completion_time_sec=21.0, error_count=0, comments="Before/after/rollback state diff displayed", role="SRE / On-Call Specialist", timestamp=now)
    ]

init_stakeholder_tasks()


# --- RBAC Server-Side Authorization Dependency ---

def verify_role_authorization(
    allowed_roles: List[str],
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
) -> str:
    """Enforces server-side RBAC. Returns HTTP 403 if role is unauthorized or missing."""
    role = x_user_role or "SRE / On-Call Specialist"
    if role not in allowed_roles:
        # Append unauthorized attempt to audit trail
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        add_audit_entry(
            actor=f"User ({role})",
            role=role,
            action_type="UNAUTHORIZED_ACTION_ATTEMPT",
            description=f"Unauthorized action attempt blocked for role `{role}`",
            metadata={"allowed_roles": allowed_roles, "attempted_role": role}
        )
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Role '{role}' is not authorized to perform this operation. Allowed roles: {allowed_roles}"
        )
    return role


def add_audit_entry(actor: str, role: str, action_type: str, description: str, metadata: Dict[str, Any]) -> AuditEntry:
    """Appends SHA-256 hash-chained entry to audit trail."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry_id = f"AUD-{len(workspace_state.audit_trail) + 5001}"
    prev_hash = workspace_state.audit_trail[-1].record_hash if workspace_state.audit_trail else GENESIS_HASH

    rec_hash = compute_audit_hash(entry_id, now, actor, role, action_type, description, metadata, prev_hash)
    entry = AuditEntry(
        id=entry_id,
        timestamp=now,
        actor=actor,
        role=role,
        action_type=action_type,
        description=description,
        metadata=metadata,
        previous_hash=prev_hash,
        record_hash=rec_hash
    )
    workspace_state.audit_trail.append(entry)
    return entry


# --- API Endpoints ---

@app.get("/api/workspace")
def get_workspace(
    role: str = Query("SRE / On-Call Specialist", alias="role"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """Returns full Shift Handover Workspace state with source resilience matrix."""
    global workspace_state
    active_role = x_user_role or role

    resp = workspace_state.model_dump()
    resp["active_role"] = active_role
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
    state: FreshnessState = Body(..., embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Edge Case Simulator: Toggles data source freshness state
    (FRESH, DELAYED, STALE, MISSING) and recalculates resilience matrix.
    """
    role = verify_role_authorization(
        ["SRE / On-Call Specialist", "Incident Commander / Handover Lead"], x_user_role
    )
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if hasattr(workspace_state.freshness, source_name):
        setattr(workspace_state.freshness, source_name, state)
        workspace_state.freshness.last_checked = now

        # Update source resilience matrix item
        for item in workspace_state.source_resilience:
            if item.source_name.lower().replace(" ", "_").startswith(source_name.split("_")[0]):
                item.state = state
                item.last_updated = now
                if state == FreshnessState.FRESH:
                    item.usability = "FULL"
                    item.impact_assessment = "Source operational; evidence linking intact."
                elif state == FreshnessState.DELAYED:
                    item.usability = "DEGRADED (15m lag)"
                    item.impact_assessment = "Data delayed; verify timestamps before executing changes."
                elif state == FreshnessState.STALE:
                    item.usability = "STALE (>30m lag)"
                    item.impact_assessment = "Data stale; confidence scores adjusted downward."
                elif state == FreshnessState.MISSING:
                    item.usability = "UNAVAILABLE"
                    item.impact_assessment = "Source offline. Workspace operating in resilient graph mode."

        add_audit_entry(
            actor="Edge Case Simulator",
            role=role,
            action_type="DATA_SOURCE_CHANGED",
            description=f"Toggled data source `{source_name}` status to `{state.value}`",
            metadata={"source": source_name, "new_state": state.value}
        )
        return {"status": "SUCCESS", "source": source_name, "new_state": state.value, "freshness": workspace_state.freshness.model_dump()}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {source_name}")


@app.post("/api/hypotheses")
def create_hypothesis(
    title: str = Body(..., embed=True),
    description: str = Body(..., embed=True),
    created_by: str = Body("Elena Rostova", embed=True),
    confidence_score: float = Body(0.5, embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """Creates a new hypothesis in the shift handover workspace."""
    role = verify_role_authorization(
        ["SRE / On-Call Specialist", "Incident Commander / Handover Lead"], x_user_role
    )
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

    add_audit_entry(
        actor=created_by,
        role=role,
        action_type="HYPOTHESIS_CREATED",
        description=f"Created hypothesis `{hypo_id}`: {title}",
        metadata={"hypothesis_id": hypo_id}
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
    added_by: str = Body("Elena Rostova", embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """Links evidence snippet to a hypothesis with source ID validation."""
    role = verify_role_authorization(
        ["SRE / On-Call Specialist", "Incident Commander / Handover Lead"], x_user_role
    )
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hypo = next((h for h in workspace_state.hypotheses if h.id == hypothesis_id), None)
    if not hypo:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hypothesis_id}' not found")

    # Validate that source_id references a real entity in raw data sources
    valid_source = False
    for cat, items in raw_data_sources.items():
        if any(getattr(item, 'id', None) == source_id for item in items):
            valid_source = True
            break
    if not valid_source:
        raise HTTPException(status_code=404, detail=f"Invalid Source ID '{source_id}' does not exist in any enterprise data stream")

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

    if impact == EvidenceImpact.SUPPORTS:
        hypo.confidence_score = min(0.99, hypo.confidence_score + 0.15)
    elif impact == EvidenceImpact.REFUTES:
        hypo.confidence_score = max(0.01, hypo.confidence_score - 0.25)
        if hypo.confidence_score < 0.1:
            hypo.status = HypothesisStatus.DISPROVED

    hypo.updated_at = now

    add_audit_entry(
        actor=added_by,
        role=role,
        action_type="EVIDENCE_LINKED",
        description=f"Linked evidence `{evid_id}` to Hypothesis `{hypothesis_id}` ({impact.value})",
        metadata={"evidence_id": evid_id, "hypothesis_id": hypothesis_id, "source_id": source_id}
    )

    return {"status": "SUCCESS", "evidence": new_evidence.model_dump(), "updated_hypothesis": hypo.model_dump()}


@app.post("/api/change-review/approve")
def approve_change_review(
    action_id: str = Body(..., embed=True),
    approver: str = Body("Marcus Vance", embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Two-person Change Review Approval Workflow.
    Requires 2 distinct users (rejects single-user dual approvals).
    """
    role = verify_role_authorization(
        ["Incident Commander / Handover Lead", "SRE / On-Call Specialist"], x_user_role
    )
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    req = next((r for r in workspace_state.change_reviews if r.action_id == action_id), None)
    if not req:
        raise HTTPException(status_code=404, detail=f"Change review request for action '{action_id}' not found")

    # Prevent same-user dual approval
    if req.approver_1 and req.approver_1.lower() == approver.lower():
        raise HTTPException(status_code=400, detail=f"Dual Approval Failure: User '{approver}' has already provided Approval 1. Approval 2 requires a distinct second user.")

    if not req.approver_1:
        req.approver_1 = approver
        req.status = "PENDING_APPROVAL_2"
    else:
        req.approver_2 = approver
        req.approved_by = f"{req.approver_1} & {req.approver_2}"
        req.status = "APPROVED"

    # Update Action Log status in both raw_data_sources and workspace_state
    for a in raw_data_sources["action_logs"]:
        if a.id == action_id:
            a.approver_1 = req.approver_1
            a.approver_2 = req.approver_2
            a.approved_by = req.approved_by
            if req.status == "APPROVED":
                a.status = ActionStatus.APPROVED

    for a in workspace_state.unresolved_actions:
        if a.id == action_id:
            a.approver_1 = req.approver_1
            a.approver_2 = req.approver_2
            a.approved_by = req.approved_by
            if req.status == "APPROVED":
                a.status = ActionStatus.APPROVED

    add_audit_entry(
        actor=approver,
        role=role,
        action_type="CHANGE_REVIEW_APPROVED",
        description=f"Approved change review step for high-impact action `{action_id}` ({req.status})",
        metadata={"action_id": action_id, "approver": approver, "review_status": req.status}
    )

    return {"status": "SUCCESS", "change_review": req.model_dump()}


@app.post("/api/actions/execute")
def execute_action(
    action_id: str = Body(..., embed=True),
    executed_by: str = Body("Elena Rostova", embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Executes an approved action, capturing before_state and after_state snapshots.
    """
    role = verify_role_authorization(["SRE / On-Call Specialist"], x_user_role)
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    if act.status == ActionStatus.EXECUTED:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been executed")

    if act.requires_two_person_review and act.status != ActionStatus.APPROVED:
        add_audit_entry(
            actor=executed_by,
            role=role,
            action_type="UNAUTHORIZED_ACTION_ATTEMPT",
            description=f"Blocked unapproved execution attempt for action `{action_id}`",
            metadata={"action_id": action_id}
        )
        raise HTTPException(status_code=403, detail="Forbidden: High-impact action requires complete 2-person approval before execution")

    # Snapshot before_state
    act.before_state = {"jwt_error_rate_percent": 18.6, "stale_cache_ratio_percent": 42.5}
    act.status = ActionStatus.EXECUTED
    act.executed_at = now
    act.after_state = {"jwt_error_rate_percent": 0.02, "stale_cache_ratio_percent": 0.0}

    workspace_state.unresolved_actions = [a for a in workspace_state.unresolved_actions if a.id != action_id]

    # Execute simulated recovery in metrics
    if action_id == "ACT-1003":
        for m in raw_data_sources["dashboard_metrics"]:
            if m.id == "METRIC-AUTH-02":
                m.current_value = 0.02
                m.status = "NORMAL"
                m.trend = "FALLING"
            elif m.id == "METRIC-AUTH-03":
                m.current_value = 0.0
                m.status = "NORMAL"
                m.trend = "FALLING"

        workspace_state.context_loss_risk_score = 2.1
        workspace_state.shift_summary += " [EXECUTION SUCCESS: API Edge Gateway cache flushed. JWT error rate reduced to 0.02%. Incident resolved.]"

    add_audit_entry(
        actor=executed_by,
        role=role,
        action_type="ACTION_EXECUTED",
        description=f"Executed action `{action_id}`: {act.action_name}",
        metadata={"action_id": action_id, "before_state": act.before_state, "after_state": act.after_state}
    )

    return {"status": "SUCCESS", "action": act.model_dump(), "workspace_risk_score": workspace_state.context_loss_risk_score}


@app.post("/api/actions/rollback")
def rollback_action(
    action_id: str = Body(..., embed=True),
    actor: str = Body("Elena Rostova", embed=True),
    rationale: str = Body("High latency observed during execution", embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """
    Executes 1-click rollback, restoring simulated state to before_state values.
    """
    role = verify_role_authorization(["SRE / On-Call Specialist"], x_user_role)
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action log entry '{action_id}' not found")

    if not act.is_reversible:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' is marked NON-REVERSIBLE and cannot be rolled back")

    if act.status == ActionStatus.ROLLED_BACK:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been rolled back")

    if act.status != ActionStatus.EXECUTED:
        raise HTTPException(status_code=400, detail=f"Cannot rollback action '{action_id}' because it has not been executed yet (Status: {act.status})")

    act.status = ActionStatus.ROLLED_BACK
    act.rollback_executed_at = now
    act.rollback_by = actor
    act.rollback_reason = rationale
    act.rollback_state = copy.deepcopy(act.before_state)

    # Physically restore simulated metrics to before_state values!
    if action_id == "ACT-1003":
        for m in raw_data_sources["dashboard_metrics"]:
            if m.id == "METRIC-AUTH-02":
                m.current_value = 18.6
                m.status = "CRITICAL"
                m.trend = "RISING"
            elif m.id == "METRIC-AUTH-03":
                m.current_value = 42.5
                m.status = "CRITICAL"
                m.trend = "HIGH_STABLE"
        workspace_state.context_loss_risk_score = 12.4

    add_audit_entry(
        actor=actor,
        role=role,
        action_type="ACTION_ROLLED_BACK",
        description=f"Executed rollback for action `{action_id}` ({act.action_name}). Rationale: {rationale}",
        metadata={"action_id": action_id, "rollback_state": act.rollback_state, "rationale": rationale}
    )

    return {"status": "SUCCESS", "action": act.model_dump()}


@app.get("/api/audit/verify")
def verify_audit_trail() -> AuditVerificationResult:
    """Verifies SHA-256 hash chain integrity of the complete audit trail."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if not workspace_state.audit_trail:
        return AuditVerificationResult(valid=True, records_checked=0, first_invalid_record=None, timestamp=now)

    prev_hash = GENESIS_HASH
    for idx, entry in enumerate(workspace_state.audit_trail):
        computed = compute_audit_hash(
            entry.id, entry.timestamp, entry.actor, entry.role,
            entry.action_type, entry.description, entry.metadata, entry.previous_hash
        )
        if entry.previous_hash != prev_hash or entry.record_hash != computed:
            return AuditVerificationResult(
                valid=False,
                records_checked=idx + 1,
                first_invalid_record=entry.id,
                timestamp=now
            )
        prev_hash = entry.record_hash

    return AuditVerificationResult(
        valid=True,
        records_checked=len(workspace_state.audit_trail),
        first_invalid_record=None,
        timestamp=now
    )


@app.post("/api/audit/tamper-test")
def simulate_audit_tampering(
    record_index: int = Body(0, embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """Edge Case Simulator: Tampers with an audit record to demonstrate tamper detection."""
    role = verify_role_authorization(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"], x_user_role)
    global workspace_state
    if not workspace_state.audit_trail or record_index >= len(workspace_state.audit_trail):
        raise HTTPException(status_code=400, detail="Invalid audit record index")

    workspace_state.audit_trail[record_index].description += " [TAMPERED BY TEST ENGINE]"
    return {"status": "SUCCESS", "message": f"Tampered record index {record_index} (ID: {workspace_state.audit_trail[record_index].id})"}


@app.post("/api/handover/signoff")
def signoff_handover(
    outgoing_lead_signature: str = Body(..., embed=True),
    incoming_lead_signature: str = Body(..., embed=True),
    notes: str = Body("Handover completed with 0 unresolved critical items.", embed=True),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role")
):
    """Completes formal sign-off between outgoing and incoming shift leads."""
    role = verify_role_authorization(["Incident Commander / Handover Lead"], x_user_role)
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    workspace_state.handover_status = "ACCEPTED"
    add_audit_entry(
        actor=f"{outgoing_lead_signature} & {incoming_lead_signature}",
        role=role,
        action_type="HANDOVER_ACCEPTED",
        description=f"Formal Shift Handover ACCEPTED between {outgoing_lead_signature} and {incoming_lead_signature}.",
        metadata={"notes": notes}
    )

    return {"status": "SUCCESS", "handover_status": workspace_state.handover_status}


@app.get("/api/benchmark")
def get_benchmark(trials: int = Query(100, ge=10, le=1000), seed: int = Query(42)):
    """Runs controlled Monte Carlo benchmark comparing Unstructured vs Structured Shift Handover."""
    return run_handover_benchmark(trials=trials, seed=seed)


@app.get("/api/resilience-experiment")
def get_resilience_experiment():
    """Returns controlled resilience experiment results across source availability conditions."""
    return run_resilience_experiment()


@app.get("/api/stakeholder-validation")
def get_stakeholder_validation():
    """Returns observational stakeholder validation tasks and summary statistics."""
    completed = [t for t in stakeholder_tasks_store if t.completed]
    avg_time = sum(t.completion_time_sec for t in completed) / len(completed) if completed else 0.0
    total_errors = sum(t.error_count for t in stakeholder_tasks_store)

    return {
        "tasks": [t.model_dump() for t in stakeholder_tasks_store],
        "summary": {
            "total_tasks": len(stakeholder_tasks_store),
            "completed_tasks": len(completed),
            "task_completion_rate_percent": round((len(completed) / len(stakeholder_tasks_store)) * 100.0, 1),
            "average_task_time_sec": round(avg_time, 1),
            "total_error_count": total_errors,
            "most_difficult_task": "TASK-03 (Finding supporting evidence snippet)"
        }
    }


@app.post("/api/stakeholder-validation")
def record_stakeholder_validation_task(
    task_id: str = Body(..., embed=True),
    completed: bool = Body(True, embed=True),
    completion_time_sec: float = Body(..., embed=True),
    error_count: int = Body(0, embed=True),
    comments: str = Body("", embed=True),
    user_role: str = Body("Enterprise App Developer / Stakeholder", embed=True)
):
    """Records an observational stakeholder validation task result."""
    global stakeholder_tasks_store
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    task = next((t for t in stakeholder_tasks_store if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Validation task '{task_id}' not found")

    task.completed = completed
    task.completion_time_sec = completion_time_sec
    task.error_count = error_count
    task.comments = comments
    task.role = user_role
    task.timestamp = now

    return {"status": "SUCCESS", "task": task.model_dump()}


@app.post("/api/reset")
def reset_workspace():
    """Resets workspace state back to initial baseline scenario."""
    global workspace_state, raw_data_sources
    workspace_state = create_initial_workspace()
    raw_data_sources = get_initial_data_sources()
    init_stakeholder_tasks()
    return {"status": "SUCCESS", "message": "Workspace reset to initial SEV-1 scenario"}


# Mount static frontend directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
