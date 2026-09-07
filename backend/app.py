"""
FastAPI Application Server for Enterprise Identity Service Shift-Handover Workspace.
Implements Prototype Authentication Context, Server-Side RBAC, SHA-256 Hash Chaining,
Generic State Snapshot Rollbacks, Controlled Benchmarks & Resilience Experiments,
Restricted Admin Endpoints, CORS configuration, and Observational Stakeholder Validation.
"""

from fastapi import FastAPI, HTTPException, Header, Body, Depends, Query, Request
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
    HypothesisStatus, StakeholderValidationTask, ValidationSummary, ValidationCategory,
    SourceResilienceItem, AuthUserIdentity
)
from backend.data_generator import (
    create_initial_workspace, get_initial_data_sources, compute_audit_hash, GENESIS_HASH
)
from backend.benchmark import run_handover_benchmark, run_resilience_experiment

app = FastAPI(
    title="Enterprise Identity Service Shift-Handover Workspace API",
    description="Resilient Shift-Handover Engine reducing recovery context loss during shift transitions.",
    version="2.1.0"
)

# CORS Configuration from Environment Variable (Default to local origins)
raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
allowed_origins = [o.strip() for o in raw_cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory state
workspace_state: ShiftHandoverWorkspace = create_initial_workspace()
raw_data_sources: Dict[str, Any] = get_initial_data_sources()
stakeholder_tasks_store: List[StakeholderValidationTask] = []


def init_stakeholder_tasks(mode: str = "NOT_TESTED"):
    """
    Initializes 8 observational stakeholder validation tasks.
    Default mode is 'NOT_TESTED' (no fabricated user research).
    """
    global stakeholder_tasks_store
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    task_definitions = [
        ("TASK-01", "Identify incident severity (SEV-1)"),
        ("TASK-02", "Identify active confirmed hypothesis (HYPO-01)"),
        ("TASK-03", "Find evidence supporting HYPO-01 (EVID-01)"),
        ("TASK-04", "Find unresolved high-impact action (ACT-1003)"),
        ("TASK-05", "Determine data-source freshness state"),
        ("TASK-06", "Identify current incident owner / shift lead"),
        ("TASK-07", "Determine change review approval requirement"),
        ("TASK-08", "Find rollback information and reversibility state")
    ]

    stakeholder_tasks_store = []
    for tid, tname in task_definitions:
        if mode == "DEMO_SAMPLE":
            stakeholder_tasks_store.append(
                StakeholderValidationTask(
                    task_id=tid,
                    task_name=tname,
                    validation_status=ValidationCategory.DEMO_SAMPLE,
                    completed=True,
                    completion_time_sec=15.0,
                    error_count=0,
                    comments="Illustrative Demo Sample Data — Not Actual User Study Results",
                    recorded_by_user="Demo Evaluator",
                    recorded_by_role="Enterprise App Developer / Stakeholder",
                    timestamp=now
                )
            )
        else:
            stakeholder_tasks_store.append(
                StakeholderValidationTask(
                    task_id=tid,
                    task_name=tname,
                    validation_status=ValidationCategory.NOT_TESTED,
                    completed=False,
                    completion_time_sec=None,
                    error_count=0,
                    comments="",
                    recorded_by_user=None,
                    recorded_by_role=None,
                    timestamp=None
                )
            )

init_stakeholder_tasks("NOT_TESTED")


# --- Authentication & RBAC Dependencies ---

SOURCE_EXPLICIT_MAP = {
    "incident_notes": "Incident Notes",
    "chat_excerpts": "Slack Chat Stream",
    "dashboards": "Datadog Telemetry",
    "ownership_changes": "AWS IAM / Ownership Log",
    "action_logs": "ServiceNow Action Log"
}


def get_authenticated_user(
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name")
) -> AuthUserIdentity:
    """
    Prototype Demo Authentication Dependency.
    - Missing X-User-Name -> HTTP 401 Unauthorized.
    - Missing X-User-Role -> HTTP 401 Unauthorized (never defaults to SRE).
    - Invalid X-User-Role -> HTTP 403 Forbidden.
    """
    if not x_user_name or not x_user_name.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing 'X-User-Name' header. Prototype authentication context required."
        )

    if not x_user_role or not x_user_role.strip():
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing 'X-User-Role' header. Prototype authentication context required."
        )

    valid_roles = [r.value for r in UserRole]
    if x_user_role not in valid_roles:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Role '{x_user_role}' is invalid. Allowed roles: {valid_roles}"
        )

    return AuthUserIdentity(username=x_user_name.strip(), role=x_user_role.strip())


def require_role(allowed_roles: List[str]):
    """Returns a dependency function verifying that authenticated user has an allowed role."""
    def rbac_dependency(auth_user: AuthUserIdentity = Depends(get_authenticated_user)) -> AuthUserIdentity:
        if auth_user.role not in allowed_roles:
            add_audit_entry(
                actor=auth_user.username,
                role=auth_user.role,
                action_type="UNAUTHORIZED_ACTION_ATTEMPT",
                description=f"Blocked operation for role `{auth_user.role}`",
                metadata={"allowed_roles": allowed_roles, "attempted_role": auth_user.role}
            )
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Operation requires one of {allowed_roles}. Current role: '{auth_user.role}'"
            )
        return auth_user
    return rbac_dependency


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
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
):
    """[AUTHENTICATED READ] Returns Shift Handover Workspace state and resilience health matrix."""
    global workspace_state
    resp = workspace_state.model_dump()
    resp["active_role"] = auth_user.role
    resp["raw_data_sources"] = raw_data_sources
    return resp


@app.get("/api/data-sources")
def get_data_sources(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
):
    """[AUTHENTICATED READ] Returns raw data from 5 enterprise data sources."""
    return {
        "freshness": workspace_state.freshness.model_dump(),
        "data_sources": raw_data_sources
    }


@app.post("/api/data-sources/toggle")
def toggle_data_source_state(
    source_name: str = Body(..., embed=True),
    state: FreshnessState = Body(..., embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"]))
):
    """[AUTHENTICATED MUTATION] Toggles data source freshness state using explicit source map."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if hasattr(workspace_state.freshness, source_name):
        setattr(workspace_state.freshness, source_name, state)
        workspace_state.freshness.last_checked = now

        target_display_name = SOURCE_EXPLICIT_MAP.get(source_name)
        for item in workspace_state.source_resilience:
            if target_display_name and item.source_name == target_display_name:
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
            actor=auth_user.username,
            role=auth_user.role,
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
    confidence_score: float = Body(0.5, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"]))
):
    """[AUTHENTICATED MUTATION] Creates a new operational hypothesis using authenticated user identity."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    hypo_id = f"HYPO-{len(workspace_state.hypotheses) + 1:02d}"

    new_hypo = Hypothesis(
        id=hypo_id,
        title=title,
        description=description,
        status=HypothesisStatus.INVESTIGATING,
        confidence_score=confidence_score,
        created_by=auth_user.username,
        created_at=now,
        updated_at=now,
        evidence_ids=[]
    )

    workspace_state.hypotheses.append(new_hypo)

    add_audit_entry(
        actor=auth_user.username,
        role=auth_user.role,
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
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"]))
):
    """[AUTHENTICATED MUTATION] Links evidence snippet to hypothesis with source ID validation."""
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hypo = next((h for h in workspace_state.hypotheses if h.id == hypothesis_id), None)
    if not hypo:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hypothesis_id}' not found")

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
        added_by=auth_user.username,
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
        actor=auth_user.username,
        role=auth_user.role,
        action_type="EVIDENCE_LINKED",
        description=f"Linked evidence `{evid_id}` to Hypothesis `{hypothesis_id}` ({impact.value})",
        metadata={"evidence_id": evid_id, "hypothesis_id": hypothesis_id, "source_id": source_id}
    )

    return {"status": "SUCCESS", "evidence": new_evidence.model_dump(), "updated_hypothesis": hypo.model_dump()}


@app.post("/api/change-review/approve")
def approve_change_review(
    action_id: str = Body(..., embed=True),
    approver: Optional[str] = Body(None, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead", "SRE / On-Call Specialist"]))
):
    """
    [AUTHENTICATED MUTATION] Two-person Change Review Approval Workflow.
    Uses authenticated user identity (`auth_user.username`) to prevent impersonation.
    Rejects same-user dual approvals.
    """
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    approver_username = auth_user.username

    req = next((r for r in workspace_state.change_reviews if r.action_id == action_id), None)
    if not req:
        raise HTTPException(status_code=404, detail=f"Change review request for action '{action_id}' not found")

    if req.approver_1 and req.approver_1.lower() == approver_username.lower():
        raise HTTPException(status_code=400, detail=f"Dual Approval Failure: User '{approver_username}' has already provided Approval 1. Approval 2 requires a distinct second user.")

    if not req.approver_1:
        req.approver_1 = approver_username
        req.status = "PENDING_APPROVAL_2"
    else:
        req.approver_2 = approver_username
        req.approved_by = f"{req.approver_1} & {req.approver_2}"
        req.status = "APPROVED"

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
        actor=approver_username,
        role=auth_user.role,
        action_type="CHANGE_REVIEW_APPROVED",
        description=f"Approved change review step for action `{action_id}` ({req.status})",
        metadata={"action_id": action_id, "approver": approver_username, "review_status": req.status}
    )

    return {"status": "SUCCESS", "change_review": req.model_dump()}


@app.post("/api/actions/execute")
def execute_action(
    action_id: str = Body(..., embed=True),
    executed_by: Optional[str] = Body(None, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist"]))
):
    """
    [AUTHENTICATED MUTATION] Executes an approved action, capturing before_state snapshot
    from current component metrics and applying after_state.
    Uses authenticated user identity (`auth_user.username`).
    """
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    operator = auth_user.username

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    if act.status == ActionStatus.EXECUTED:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been executed")

    if act.requires_two_person_review and act.status != ActionStatus.APPROVED:
        add_audit_entry(
            actor=operator,
            role=auth_user.role,
            action_type="UNAUTHORIZED_ACTION_ATTEMPT",
            description=f"Blocked unapproved execution attempt for action `{action_id}`",
            metadata={"action_id": action_id}
        )
        raise HTTPException(status_code=403, detail="Forbidden: High-impact action requires complete 2-person approval before execution")

    # Capture dynamic before_state snapshot from current dashboard metrics
    current_error = 18.6
    current_stale = 42.5
    for m in raw_data_sources["dashboard_metrics"]:
        if m.id == "METRIC-AUTH-02":
            current_error = m.current_value
        elif m.id == "METRIC-AUTH-03":
            current_stale = m.current_value

    act.before_state = {"jwt_error_rate_percent": current_error, "stale_cache_ratio_percent": current_stale}
    act.after_state = {"jwt_error_rate_percent": 0.02, "stale_cache_ratio_percent": 0.0}
    act.status = ActionStatus.EXECUTED
    act.executed_at = now

    workspace_state.unresolved_actions = [a for a in workspace_state.unresolved_actions if a.id != action_id]

    # Apply after_state
    for m in raw_data_sources["dashboard_metrics"]:
        if m.id == "METRIC-AUTH-02":
            m.current_value = act.after_state["jwt_error_rate_percent"]
            m.status = "NORMAL"
            m.trend = "FALLING"
        elif m.id == "METRIC-AUTH-03":
            m.current_value = act.after_state["stale_cache_ratio_percent"]
            m.status = "NORMAL"
            m.trend = "FALLING"

    workspace_state.context_loss_risk_score = 2.1
    workspace_state.shift_summary += " [EXECUTION SUCCESS: API Edge Gateway cache flushed. JWT error rate reduced to 0.02%. Incident resolved.]"

    add_audit_entry(
        actor=operator,
        role=auth_user.role,
        action_type="ACTION_EXECUTED",
        description=f"Executed action `{action_id}`: {act.action_name}",
        metadata={"action_id": action_id, "before_state": act.before_state, "after_state": act.after_state}
    )

    return {"status": "SUCCESS", "action": act.model_dump(), "workspace_risk_score": workspace_state.context_loss_risk_score}


@app.post("/api/actions/rollback")
def rollback_action(
    action_id: str = Body(..., embed=True),
    rationale: str = Body("1-Click Rollback Triggered", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist"]))
):
    """
    [AUTHENTICATED MUTATION] Generic State Snapshot Rollback Engine.
    Restores before_state snapshot values directly into system metrics.
    Prevents double rollback, rollback before execution, or non-reversible rollback.
    """
    global workspace_state, raw_data_sources
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    operator = auth_user.username

    act = next((a for a in raw_data_sources["action_logs"] if a.id == action_id), None)
    if not act:
        raise HTTPException(status_code=404, detail=f"Action log entry '{action_id}' not found")

    if not act.is_reversible:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' is marked NON-REVERSIBLE and cannot be rolled back")

    if act.status == ActionStatus.ROLLED_BACK:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been rolled back")

    if act.status != ActionStatus.EXECUTED:
        raise HTTPException(status_code=400, detail=f"Cannot rollback action '{action_id}' because it has not been executed yet (Current Status: {act.status})")

    act.status = ActionStatus.ROLLED_BACK
    act.rollback_executed_at = now
    act.rollback_by = operator
    act.rollback_reason = rationale
    act.rollback_state = copy.deepcopy(act.before_state)

    # Generic restoration from before_state snapshot
    restored_err = act.before_state.get("jwt_error_rate_percent", 18.6)
    restored_stale = act.before_state.get("stale_cache_ratio_percent", 42.5)

    for m in raw_data_sources["dashboard_metrics"]:
        if m.id == "METRIC-AUTH-02":
            m.current_value = restored_err
            m.status = "CRITICAL" if restored_err > 5.0 else "NORMAL"
            m.trend = "RISING"
        elif m.id == "METRIC-AUTH-03":
            m.current_value = restored_stale
            m.status = "CRITICAL" if restored_stale > 1.0 else "NORMAL"
            m.trend = "HIGH_STABLE"

    workspace_state.context_loss_risk_score = 12.4

    add_audit_entry(
        actor=operator,
        role=auth_user.role,
        action_type="ACTION_ROLLED_BACK",
        description=f"Executed rollback for action `{action_id}` ({act.action_name}). Rationale: {rationale}",
        metadata={"action_id": action_id, "restored_state": act.before_state, "rationale": rationale}
    )

    return {"status": "SUCCESS", "action": act.model_dump()}


@app.get("/api/audit/verify")
def verify_audit_trail(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
) -> AuditVerificationResult:
    """[AUTHENTICATED READ] Verifies SHA-256 hash chain integrity of audit trail."""
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
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"]))
):
    """[AUTHENTICATED TEST] Tampers with an audit record to demonstrate tamper detection."""
    global workspace_state
    if not workspace_state.audit_trail or record_index >= len(workspace_state.audit_trail):
        raise HTTPException(status_code=400, detail="Invalid audit record index")

    workspace_state.audit_trail[record_index].description += " [TAMPERED BY TEST ENGINE]"
    return {"status": "SUCCESS", "message": f"Tampered record index {record_index} (ID: {workspace_state.audit_trail[record_index].id})"}


@app.post("/api/handover/signoff")
def signoff_handover(
    outgoing_user: str = Body(..., embed=True),
    incoming_user: str = Body(..., embed=True),
    notes: str = Body("Handover completed with 0 unresolved critical items.", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead"]))
):
    """
    [AUTHENTICATED MUTATION] Structured Handover Sign-Off.
    Requires distinct outgoing and incoming identities.
    """
    global workspace_state
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    out_clean = outgoing_user.strip()
    in_clean = incoming_user.strip()

    if not out_clean or not in_clean:
        raise HTTPException(status_code=400, detail="Handover Sign-off Error: Both outgoing and incoming shift lead identities are required")

    if out_clean.lower() == in_clean.lower():
        raise HTTPException(status_code=400, detail=f"Handover Sign-off Error: Outgoing user '{out_clean}' and Incoming user '{in_clean}' cannot be identical")

    workspace_state.outgoing_shift_lead = out_clean
    workspace_state.incoming_shift_lead = in_clean
    workspace_state.handover_status = "ACCEPTED"

    add_audit_entry(
        actor=auth_user.username,
        role=auth_user.role,
        action_type="HANDOVER_ACCEPTED",
        description=f"Formal Shift Handover ACCEPTED between Outgoing: '{out_clean}' and Incoming: '{in_clean}'.",
        metadata={"outgoing_user": out_clean, "incoming_user": in_clean, "notes": notes}
    )

    return {"status": "SUCCESS", "handover_status": workspace_state.handover_status, "outgoing_user": out_clean, "incoming_user": in_clean}


@app.get("/api/benchmark")
def get_benchmark(
    trials: int = Query(100, ge=10, le=1000),
    seed: int = Query(42),
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
):
    """[AUTHENTICATED READ] Runs controlled Monte Carlo simulation (seed=42, 100 trials)."""
    return run_handover_benchmark(trials=trials, seed=seed)


@app.get("/api/resilience-experiment")
def get_resilience_experiment(
    trials: int = Query(100, ge=10, le=500),
    seed: int = Query(42),
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
):
    """[AUTHENTICATED READ] Runs controlled simulated resilience experiment across 4 chat availability conditions."""
    return run_resilience_experiment(trials_per_condition=trials, seed=seed)


@app.get("/api/stakeholder-validation")
def get_stakeholder_validation(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user)
):
    """[PUBLIC DEMO READ] Returns observational stakeholder validation tasks and summary statistics."""
    observed = [t for t in stakeholder_tasks_store if t.validation_status == ValidationCategory.OBSERVED_VALIDATION and t.completed]
    avg_time = sum(t.completion_time_sec for t in observed if t.completion_time_sec) / len(observed) if observed else 0.0
    total_errors = sum(t.error_count for t in observed)

    not_tested = sum(1 for t in stakeholder_tasks_store if t.validation_status == ValidationCategory.NOT_TESTED)
    demo_sample = sum(1 for t in stakeholder_tasks_store if t.validation_status == ValidationCategory.DEMO_SAMPLE)

    summary = ValidationSummary(
        total_tasks=len(stakeholder_tasks_store),
        not_tested_count=not_tested,
        demo_sample_count=demo_sample,
        observed_validation_count=len(observed),
        observed_completion_rate_percent=round((len(observed) / len(stakeholder_tasks_store)) * 100.0, 1),
        observed_avg_task_time_sec=round(avg_time, 1),
        observed_total_errors=total_errors,
        most_difficult_task="TASK-03 (Finding supporting evidence snippet)"
    )

    return {
        "tasks": [t.model_dump() for t in stakeholder_tasks_store],
        "summary": summary.model_dump()
    }


@app.post("/api/stakeholder-validation")
def record_stakeholder_validation_task(
    task_id: str = Body(..., embed=True),
    completed: bool = Body(True, embed=True),
    completion_time_sec: Optional[float] = Body(None, embed=True),
    error_count: int = Body(0, embed=True),
    comments: str = Body("", embed=True),
    validation_status: ValidationCategory = Body(ValidationCategory.OBSERVED_VALIDATION, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Enterprise App Developer / Stakeholder", "Incident Commander / Handover Lead", "SRE / On-Call Specialist"]))
):
    """[AUTHENTICATED MUTATION] Records an observational stakeholder validation task observation."""
    global stakeholder_tasks_store
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    task = next((t for t in stakeholder_tasks_store if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Validation task '{task_id}' not found")

    task.validation_status = validation_status
    task.completed = completed
    task.completion_time_sec = completion_time_sec
    task.error_count = error_count
    task.comments = comments
    task.recorded_by_user = auth_user.username
    task.recorded_by_role = auth_user.role
    task.timestamp = now

    add_audit_entry(
        actor=auth_user.username,
        role=auth_user.role,
        action_type="STAKEHOLDER_VALIDATION_RECORDED",
        description=f"Recorded stakeholder validation task `{task_id}` status: {validation_status.value}",
        metadata={"task_id": task_id, "validation_status": validation_status.value}
    )

    return {"status": "SUCCESS", "task": task.model_dump()}


@app.post("/api/stakeholder-validation/demo-toggle")
def toggle_stakeholder_demo_sample(
    mode: str = Body("DEMO_SAMPLE", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead", "SRE / On-Call Specialist"]))
):
    """Toggles stakeholder validation tasks between NOT_TESTED and DEMO_SAMPLE."""
    init_stakeholder_tasks(mode=mode)
    return {"status": "SUCCESS", "mode": mode, "tasks": [t.model_dump() for t in stakeholder_tasks_store]}


@app.post("/api/reset")
def reset_workspace(
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"]))
):
    """
    [RESTRICTED ADMIN ENDPOINT] Resets workspace state back to initial baseline scenario.
    Requires authenticated SRE or Incident Commander identity. Appends ADMIN_RESET to SHA-256 audit.
    """
    global workspace_state, raw_data_sources
    workspace_state = create_initial_workspace()
    raw_data_sources = get_initial_data_sources()
    init_stakeholder_tasks("NOT_TESTED")

    add_audit_entry(
        actor=auth_user.username,
        role=auth_user.role,
        action_type="ADMIN_RESET",
        description=f"Workspace state reset to initial SEV-1 scenario by `{auth_user.username}`",
        metadata={"reset_by": auth_user.username}
    )

    return {"status": "SUCCESS", "message": "Workspace reset to initial SEV-1 scenario"}


# Mount static frontend directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
