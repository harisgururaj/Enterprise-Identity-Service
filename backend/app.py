"""
FastAPI Application Server for Enterprise Identity Service Shift-Handover Workspace.
Implements SQLite Database Persistence (SQLAlchemy), Clean AuthProvider Abstraction,
Server-Side RBAC, SHA-256 Hash Chaining, Snapshot Rollbacks, Controlled Benchmarks,
Resilience Experiments, Fixture Ingestion, and Health/Readiness Monitoring.
"""

from fastapi import FastAPI, HTTPException, Header, Body, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import init_db, get_db
from backend.models import (
    ShiftHandoverWorkspace, Hypothesis, Evidence, ActionLog,
    FreshnessState, ActionStatus, UserRole, ImpactLevel, AuditEntry,
    AuditVerificationResult, ChangeReviewRequest, EvidenceImpact, SourceType,
    HypothesisStatus, StakeholderValidationTask, ValidationSummary, ValidationCategory,
    SourceResilienceItem, AuthUserIdentity
)
from backend.repository import (
    seed_database_from_fixtures,
    get_workspace_state_db,
    get_raw_data_sources_db,
    toggle_source_freshness_db,
    create_hypothesis_db,
    link_evidence_db,
    approve_change_review_db,
    execute_action_db,
    rollback_action_db,
    verify_audit_trail_db,
    tamper_test_db,
    signoff_handover_db,
    get_stakeholder_validation_db,
    record_stakeholder_task_db,
    toggle_stakeholder_demo_db,
    add_audit_entry_db
)
from backend.benchmark import run_handover_benchmark, run_resilience_experiment

app = FastAPI(
    title="Enterprise Identity Service Shift-Handover Workspace API",
    description="Resilient Shift-Handover Engine with SQLite DB Persistence, SHA-256 Hash-Chaining, and Zero Fabrication.",
    version="2.2.0"
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


# --- Startup Event: Initialize and Seed SQLite Database ---
@app.on_event("startup")
def on_startup():
    init_db()
    with next(get_db()) as db:
        seed_database_from_fixtures(db, force=False)


# --- Authentication & AuthProvider Abstraction ---

class AuthProviderInterface(ABC):
    """
    Abstract authentication provider interface separating prototype headers
    from production OAuth2 / OIDC SSO authentication.
    """
    @abstractmethod
    def get_authenticated_user(self, request: Request) -> AuthUserIdentity:
        pass


class HeaderAuthProvider(AuthProviderInterface):
    """
    Prototype authentication provider extracting identity from HTTP headers.
    Enforces strict role validation and rejects missing user/role header credentials.
    """
    def get_authenticated_user(self, request: Request) -> AuthUserIdentity:
        x_user_name = request.headers.get("X-User-Name")
        x_user_role = request.headers.get("X-User-Role")

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


class OIDCAuthProvider(AuthProviderInterface):
    """
    Production Enterprise OIDC / OAuth2 Provider boundary.
    Requires live IdP configuration (Okta, Azure AD, Keycloak) when AUTH_PROVIDER=oidc.
    """
    def get_authenticated_user(self, request: Request) -> AuthUserIdentity:
        raise HTTPException(
            status_code=501,
            detail="Not Implemented: Production Enterprise OIDC/OAuth2 authentication provider requires live IdP configuration (Okta / Azure AD / Keycloak). Set AUTH_PROVIDER=header for prototype demo mode."
        )


auth_provider_mode = os.getenv("AUTH_PROVIDER", "header").strip().lower()
if auth_provider_mode == "oidc":
    auth_provider: AuthProviderInterface = OIDCAuthProvider()
else:
    auth_provider: AuthProviderInterface = HeaderAuthProvider()


def get_authenticated_user(request: Request) -> AuthUserIdentity:
    """FastAPI dependency wrapper for the active AuthProvider."""
    return auth_provider.get_authenticated_user(request)



def require_role(allowed_roles: List[str]):
    """Returns a dependency function verifying that authenticated user has an allowed role."""
    def rbac_dependency(
        request: Request,
        db: Session = Depends(get_db)
    ) -> AuthUserIdentity:
        auth_user = auth_provider.get_authenticated_user(request)
        if auth_user.role not in allowed_roles:
            add_audit_entry_db(
                db,
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


# --- System Health & Database Readiness Endpoints ---

@app.get("/health")
def health_check():
    """Returns system status and timestamp."""
    return {
        "status": "UP",
        "service": "Enterprise Identity Service Shift-Handover Workspace",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }


@app.get("/health/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Verifies SQLite database connectivity and table readiness."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "READY",
            "database": "CONNECTED",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: Database health check failed ({str(e)})"
        )


# --- Workspace API Endpoints ---

@app.get("/api/workspace")
def get_workspace(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED READ] Returns Shift Handover Workspace state and resilience health matrix from SQLite DB."""
    ws = get_workspace_state_db(db)
    raw_sources = get_raw_data_sources_db(db)
    resp = ws.model_dump()
    resp["active_role"] = auth_user.role
    resp["raw_data_sources"] = raw_sources
    return resp


@app.get("/api/data-sources")
def get_data_sources(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED READ] Returns raw data from 5 enterprise data sources in SQLite DB."""
    ws = get_workspace_state_db(db)
    raw_sources = get_raw_data_sources_db(db)
    return {
        "freshness": ws.freshness.model_dump(),
        "data_sources": raw_sources
    }


@app.post("/api/data-sources/toggle")
def toggle_data_source_state(
    source_name: str = Body(..., embed=True),
    state: FreshnessState = Body(..., embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Toggles data source freshness state in SQLite DB."""
    return toggle_source_freshness_db(db, source_name, state, auth_user.username, auth_user.role)


@app.post("/api/fixtures/ingest")
def reingest_fixtures(
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Re-ingests 5 synthetic enterprise JSON fixtures into SQLite DB."""
    seed_database_from_fixtures(db, force=True)
    add_audit_entry_db(
        db,
        actor=auth_user.username,
        role=auth_user.role,
        action_type="FIXTURES_REINGESTED",
        description="Re-ingested synthetic enterprise JSON fixtures from data/ directory",
        metadata={"reingested_by": auth_user.username}
    )
    return {"status": "SUCCESS", "message": "Synthetic enterprise JSON fixtures re-ingested successfully"}


@app.post("/api/hypotheses")
def create_hypothesis(
    title: str = Body(..., embed=True),
    description: str = Body(..., embed=True),
    confidence_score: float = Body(0.5, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Creates a new operational hypothesis in SQLite DB."""
    return create_hypothesis_db(db, title, description, confidence_score, auth_user.username, auth_user.role)


@app.post("/api/evidence")
def link_evidence(
    hypothesis_id: str = Body(..., embed=True),
    source_type: SourceType = Body(..., embed=True),
    source_id: str = Body(..., embed=True),
    title: str = Body(..., embed=True),
    snippet: str = Body(..., embed=True),
    impact: EvidenceImpact = Body(..., embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Links evidence snippet to hypothesis in SQLite DB."""
    # Verify source_id exists in raw data sources
    raw_sources = get_raw_data_sources_db(db)
    valid_source = False
    for cat, items in raw_sources.items():
        if any(getattr(item, 'id', None) == source_id for item in items):
            valid_source = True
            break
    if not valid_source:
        raise HTTPException(status_code=404, detail=f"Invalid Source ID '{source_id}' does not exist in any enterprise data stream")

    return link_evidence_db(db, hypothesis_id, source_type, source_id, title, snippet, impact, auth_user.username, auth_user.role)


@app.post("/api/change-review/approve")
def approve_change_review(
    action_id: str = Body(..., embed=True),
    approver: Optional[str] = Body(None, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead", "SRE / On-Call Specialist"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Two-person Change Review Approval Workflow in SQLite DB."""
    return approve_change_review_db(db, action_id, auth_user.username, auth_user.role)


@app.post("/api/actions/execute")
def execute_action(
    action_id: str = Body(..., embed=True),
    executed_by: Optional[str] = Body(None, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Executes an approved action in SQLite DB with state snapshotting."""
    return execute_action_db(db, action_id, auth_user.username, auth_user.role)


@app.post("/api/actions/rollback")
def rollback_action(
    action_id: str = Body(..., embed=True),
    rationale: str = Body("1-Click Rollback Triggered", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Generic State Snapshot Rollback Engine in SQLite DB."""
    return rollback_action_db(db, action_id, rationale, auth_user.username, auth_user.role)


@app.get("/api/audit/verify")
def verify_audit_trail(
    auth_user: AuthUserIdentity = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
) -> AuditVerificationResult:
    """[AUTHENTICATED READ] Verifies SHA-256 hash chain integrity of audit records in SQLite DB."""
    return verify_audit_trail_db(db)


@app.post("/api/audit/tamper-test")
def simulate_audit_tampering(
    record_index: int = Body(0, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED TEST] Tampers with an audit record in SQLite DB to verify detection."""
    return tamper_test_db(db, record_index, auth_user.username, auth_user.role)


@app.post("/api/handover/signoff")
def signoff_handover(
    outgoing_user: str = Body(..., embed=True),
    incoming_user: str = Body(..., embed=True),
    notes: str = Body("Handover completed with 0 unresolved critical items.", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Structured Handover Sign-Off in SQLite DB."""
    return signoff_handover_db(db, outgoing_user, incoming_user, notes, auth_user.username, auth_user.role)


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
    auth_user: AuthUserIdentity = Depends(get_authenticated_user),
    db: Session = Depends(get_db)
):
    """[PUBLIC DEMO READ] Returns observational stakeholder validation tasks and summary statistics from SQLite DB."""
    return get_stakeholder_validation_db(db)


@app.post("/api/stakeholder-validation")
def record_stakeholder_validation_task(
    task_id: str = Body(..., embed=True),
    completed: bool = Body(True, embed=True),
    completion_time_sec: Optional[float] = Body(None, embed=True),
    error_count: int = Body(0, embed=True),
    comments: str = Body("", embed=True),
    validation_status: ValidationCategory = Body(ValidationCategory.OBSERVED_VALIDATION, embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Enterprise App Developer / Stakeholder", "Incident Commander / Handover Lead", "SRE / On-Call Specialist"])),
    db: Session = Depends(get_db)
):
    """[AUTHENTICATED MUTATION] Records an observational stakeholder validation task observation in SQLite DB."""
    return record_stakeholder_task_db(db, task_id, completed, completion_time_sec, error_count, comments, validation_status, auth_user.username, auth_user.role)


@app.post("/api/stakeholder-validation/demo-toggle")
def toggle_stakeholder_demo_sample(
    mode: str = Body("DEMO_SAMPLE", embed=True),
    auth_user: AuthUserIdentity = Depends(require_role(["Incident Commander / Handover Lead", "SRE / On-Call Specialist"])),
    db: Session = Depends(get_db)
):
    """Toggles stakeholder validation tasks between NOT_TESTED and DEMO_SAMPLE in SQLite DB."""
    return toggle_stakeholder_demo_db(db, mode)


@app.post("/api/reset")
def reset_workspace(
    auth_user: AuthUserIdentity = Depends(require_role(["SRE / On-Call Specialist", "Incident Commander / Handover Lead"])),
    db: Session = Depends(get_db)
):
    """
    [RESTRICTED ADMIN ENDPOINT] Resets SQLite DB workspace state back to initial baseline scenario.
    Appends ADMIN_RESET to SHA-256 audit.
    """
    seed_database_from_fixtures(db, force=True)
    add_audit_entry_db(
        db,
        actor=auth_user.username,
        role=auth_user.role,
        action_type="ADMIN_RESET",
        description=f"Workspace state reset to initial SEV-1 scenario by `{auth_user.username}`",
        metadata={"reset_by": auth_user.username}
    )
    return {"status": "SUCCESS", "message": "Workspace reset to initial SEV-1 scenario in SQLite database"}


# Mount static frontend directory
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
