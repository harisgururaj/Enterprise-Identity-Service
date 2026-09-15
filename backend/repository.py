"""
Repository Data Access Layer for Enterprise Identity Service Shift-Handover Workspace.
Handles SQLite database persistence, fixture ingestion from data/*.json,
SHA-256 audit chain validation, snapshot rollbacks, and stakeholder validation.
"""

import os
import json
import copy
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.database import init_db, SessionLocal
from backend.db_models import (
    DBIncidentWorkspace, DBIncidentNote, DBChatExcerpt, DBDashboardMetric,
    DBOwnershipChange, DBActionLog, DBHypothesis, DBEvidence,
    DBChangeReviewRequest, DBSourceResilienceItem, DBAuditEntry,
    DBFreshnessStatus, DBStakeholderTask
)
from backend.models import (
    FreshnessState, ImpactLevel, HypothesisStatus, EvidenceImpact,
    SourceType, ActionStatus, AuditEntry, AuditVerificationResult,
    DataFreshnessStatus, ChangeReviewRequest, SourceResilienceItem,
    ShiftHandoverWorkspace, ValidationCategory, StakeholderValidationTask,
    ValidationSummary, IncidentNote, ChatExcerpt, DashboardMetric,
    MetricSeriesPoint, OwnershipChange, ActionLog, Hypothesis, Evidence
)
from backend.data_generator import GENESIS_HASH, compute_audit_hash

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

SOURCE_EXPLICIT_MAP = {
    "incident_notes": "Incident Notes",
    "chat_excerpts": "Slack Chat Stream",
    "dashboards": "Datadog Telemetry",
    "ownership_changes": "AWS IAM / Ownership Log",
    "action_logs": "ServiceNow Action Log"
}


def load_fixture(filename: str) -> List[Dict[str, Any]]:
    """Loads a synthetic enterprise JSON fixture from data/ directory."""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def seed_database_from_fixtures(db: Session, force: bool = False):
    """
    Ingests 5 synthetic enterprise JSON fixtures from data/ into SQLite database tables.
    Initializes hypotheses, evidence, audit trail, and stakeholder tasks.
    """
    if not force and db.query(DBIncidentWorkspace).first() is not None:
        return  # Database already seeded

    # Clear existing data if force=True
    if force:
        db.query(DBIncidentWorkspace).delete()
        db.query(DBIncidentNote).delete()
        db.query(DBChatExcerpt).delete()
        db.query(DBDashboardMetric).delete()
        db.query(DBOwnershipChange).delete()
        db.query(DBActionLog).delete()
        db.query(DBHypothesis).delete()
        db.query(DBEvidence).delete()
        db.query(DBChangeReviewRequest).delete()
        db.query(DBSourceResilienceItem).delete()
        db.query(DBAuditEntry).delete()
        db.query(DBFreshnessStatus).delete()
        db.query(DBStakeholderTask).delete()
        db.commit()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Incident Workspace Header
    ws_db = DBIncidentWorkspace(
        id="INC-9042",
        incident_id="INC-9042",
        incident_title="SEV-1: Enterprise Core Identity Token Verification Failures",
        severity="SEV-1",
        started_at="2026-09-03T07:10:00Z",
        outgoing_shift_lead="Marcus Vance (Shift Alpha)",
        incoming_shift_lead="Elena Rostova (Shift Beta)",
        handover_status="IN_REVIEW",
        context_loss_risk_score=12.4,
        shift_summary=(
            "SEV-1 incident declared at 07:10 UTC following Vault key rotation to v4.1. Root cause confirmed with 92% confidence "
            "as API Edge Gateway JWKS key cache mismatch. Disproved hypotheses regarding Redis pool memory leak and Core Pod CPU "
            "throttling. Primary unresolved action: Execute two-person approved forced cache invalidation signal (ACT-1003). "
            "Fallback action: Key rollback to v3.9 (ACT-1004)."
        )
    )
    db.add(ws_db)

    # 2. Ingest 5 Data Sources from JSON Fixtures
    for note in load_fixture("incident_notes.json"):
        db.add(DBIncidentNote(
            id=note["id"],
            timestamp=note["timestamp"],
            author=note["author"],
            severity=note["severity"],
            summary=note["summary"],
            tags_json=json.dumps(note.get("tags", [])),
            content=note["content"],
            impacted_apps_count=note.get("impacted_apps_count", 480),
            freshness=note.get("freshness", "FRESH")
        ))

    for chat in load_fixture("slack_chat.json"):
        db.add(DBChatExcerpt(
            id=chat["id"],
            timestamp=chat["timestamp"],
            channel=chat["channel"],
            sender=chat["sender"],
            sender_role=chat["sender_role"],
            text=chat["text"],
            key_takeaway=chat.get("key_takeaway"),
            tags_json=json.dumps(chat.get("tags", [])),
            freshness=chat.get("freshness", "FRESH")
        ))

    for m in load_fixture("datadog_metrics.json"):
        db.add(DBDashboardMetric(
            id=m["id"],
            name=m["name"],
            category=m["category"],
            current_value=m["current_value"],
            unit=m["unit"],
            status=m["status"],
            baseline_value=m["baseline_value"],
            threshold_critical=m["threshold_critical"],
            trend=m["trend"],
            history_json=json.dumps(m.get("history", [])),
            freshness=m.get("freshness", "FRESH")
        ))

    for own in load_fixture("ownership_changes.json"):
        db.add(DBOwnershipChange(
            id=own["id"],
            timestamp=own["timestamp"],
            previous_lead=own["previous_lead"],
            new_lead=own["new_lead"],
            outgoing_shift=own["outgoing_shift"],
            incoming_shift=own["incoming_shift"],
            team=own["team"],
            handover_type=own["handover_type"],
            notes=own["notes"],
            freshness=own.get("freshness", "FRESH")
        ))

    for act in load_fixture("servicenow_actions.json"):
        db.add(DBActionLog(
            id=act["id"],
            timestamp=act["timestamp"],
            actor=act["actor"],
            action_name=act["action_name"],
            description=act["description"],
            target_component=act["target_component"],
            impact_level=act["impact_level"],
            status=act["status"],
            is_reversible=act.get("is_reversible", True),
            requires_two_person_review=act.get("requires_two_person_review", True),
            executed_at=act.get("executed_at"),
            approved_by=act.get("approved_by"),
            approver_1=act.get("approver_1"),
            approver_2=act.get("approver_2"),
            rollback_action_id=act.get("rollback_action_id"),
            rollback_executed_at=act.get("rollback_executed_at"),
            rollback_by=act.get("rollback_by"),
            rollback_reason=act.get("rollback_reason"),
            before_state_json=json.dumps(act.get("before_state", {})),
            after_state_json=json.dumps(act.get("after_state", {})),
            rollback_state_json=json.dumps(act.get("rollback_state", {})),
            details_json=json.dumps(act.get("details", {})),
            freshness=act.get("freshness", "FRESH")
        ))

    # 3. Seed Hypotheses and Evidence
    db.add(DBHypothesis(
        id="HYPO-01",
        title="OAuth2 Token Signing Key Rotation Desynchronization",
        description="Vault rotated identity signing key to v4.1 at 07:00 UTC, but 42.5% of API Edge Gateways missed webhook cache invalidation trigger, causing 18.6% JWT signature validation failure spike.",
        status="CONFIRMED",
        confidence_score=0.92,
        created_by="Marcus Vance",
        created_at="2026-09-03T07:20:00Z",
        updated_at="2026-09-03T08:50:00Z",
        evidence_ids_json=json.dumps(["EVID-01", "EVID-02"])
    ))

    db.add(DBHypothesis(
        id="HYPO-02",
        title="Redis Session Lock Memory Contention",
        description="Redis token session store connection pool lock contention causing authentication thread starvation.",
        status="DISPROVED",
        confidence_score=0.08,
        created_by="Devon Zhao",
        created_at="2026-09-03T07:35:00Z",
        updated_at="2026-09-03T08:12:00Z",
        evidence_ids_json=json.dumps(["EVID-03"])
    ))

    db.add(DBEvidence(
        id="EVID-01",
        hypothesis_id="HYPO-01",
        source_type="CHAT",
        source_id="CHAT-8812",
        title="API Gateway JWKS Cache Timeout",
        snippet="Priya Patel confirmed Edge Gateways hold 4-hour JWKS cache and missed invalidation webhook trigger.",
        impact="SUPPORTS",
        added_by="Marcus Vance",
        added_at="2026-09-03T07:45:00Z"
    ))

    db.add(DBEvidence(
        id="EVID-02",
        hypothesis_id="HYPO-01",
        source_type="METRIC",
        source_id="METRIC-AUTH-03",
        title="42.5% Edge Cache Stale Node Ratio",
        snippet="Metric METRIC-AUTH-03 shows exactly 42.5% of edge nodes are using stale public keys post-rotation.",
        impact="SUPPORTS",
        added_by="Marcus Vance",
        added_at="2026-09-03T07:48:00Z"
    ))

    db.add(DBEvidence(
        id="EVID-03",
        hypothesis_id="HYPO-02",
        source_type="ACTION_LOG",
        source_id="ACT-1002",
        title="Redis Connection Lock Latency Spike",
        snippet="Action ACT-1002 pool flush spiked p99 latency to 240ms without resolving 401 JWT error spike.",
        impact="REFUTES",
        added_by="Devon Zhao",
        added_at="2026-09-03T08:12:00Z"
    ))

    # 4. Seed Change Review Request
    db.add(DBChangeReviewRequest(
        action_id="ACT-1003",
        action_name="Force API Gateway JWKS Public Key Cache Invalidation",
        requested_by="Elena Rostova",
        target_component="API Edge Gateway Network",
        impact_level="HIGH",
        justification="Flushes stale v3.9 public key cache across 120 edge nodes to resolve 18.6% JWT signature validation errors.",
        proposed_at="2026-09-03T09:15:00Z",
        status="PENDING_APPROVAL"
    ))

    # 5. Seed Source Resilience Items
    resilience_items = [
        ("Incident Notes", "FRESH", "FULL", "Source operational; evidence linking intact.", 2),
        ("Slack Chat Stream", "FRESH", "FULL", "Real-time communication log operational.", 4),
        ("Datadog Telemetry", "FRESH", "FULL", "Error rates and p99 latency graphs updating normally.", 4),
        ("AWS IAM / Ownership Log", "FRESH", "FULL", "Shift leads and team handover records verified.", 1),
        ("ServiceNow Action Log", "FRESH", "FULL", "Execution status and reversibility state intact.", 4)
    ]
    for s_name, state, usability, impact, evid_cnt in resilience_items:
        db.add(DBSourceResilienceItem(
            source_name=s_name,
            state=state,
            last_updated="2026-09-03T09:30:00Z",
            usability=usability,
            impact_assessment=impact,
            evidence_count=evid_cnt
        ))

    # 6. Seed Freshness Status
    db.add(DBFreshnessStatus(
        id=1,
        incident_notes="FRESH",
        chat_excerpts="FRESH",
        dashboards="FRESH",
        ownership_changes="FRESH",
        action_logs="FRESH",
        last_checked=now
    ))

    # 7. Seed Initial SHA-256 Audit Trail
    audit_trail_raw = [
        ("AUD-5001", "2026-09-03T07:10:00Z", "Marcus Vance", "SRE / On-Call Specialist", "INCIDENT_DECLARED", "Declared SEV-1 incident for Enterprise Identity Service", {"severity": "SEV-1", "incident_id": "INC-9042"}),
        ("AUD-5002", "2026-09-03T08:10:00Z", "Marcus Vance", "SRE / On-Call Specialist", "ACTION_ROLLED_BACK", "Rolled back Redis flush operation ACT-1002 due to latency spike", {"action_id": "ACT-1002"}),
        ("AUD-5003", "2026-09-03T09:30:00Z", "System Handover Engine", "Incident Commander / Handover Lead", "HANDOVER_INITIALIZED", "Shift Handover workspace initialized for Alpha -> Beta shift transition", {"outgoing": "Marcus Vance", "incoming": "Elena Rostova"})
    ]

    prev_hash = GENESIS_HASH
    for entry_id, ts, actor, role, atype, desc, meta in audit_trail_raw:
        rec_hash = compute_audit_hash(entry_id, ts, actor, role, atype, desc, meta, prev_hash)
        db.add(DBAuditEntry(
            id=entry_id,
            timestamp=ts,
            actor=actor,
            role=role,
            action_type=atype,
            description=desc,
            metadata_json=json.dumps(meta),
            previous_hash=prev_hash,
            record_hash=rec_hash
        ))
        prev_hash = rec_hash

    # 8. Seed Stakeholder Tasks (Defaulting to NOT_TESTED)
    task_defs = [
        ("TASK-01", "Identify incident severity (SEV-1)"),
        ("TASK-02", "Identify active confirmed hypothesis (HYPO-01)"),
        ("TASK-03", "Find evidence supporting HYPO-01 (EVID-01)"),
        ("TASK-04", "Find unresolved high-impact action (ACT-1003)"),
        ("TASK-05", "Determine data-source freshness state"),
        ("TASK-06", "Identify current incident owner / shift lead"),
        ("TASK-07", "Determine change review approval requirement"),
        ("TASK-08", "Find rollback information and reversibility state")
    ]
    for tid, tname in task_defs:
        db.add(DBStakeholderTask(
            task_id=tid,
            task_name=tname,
            validation_status="NOT_TESTED",
            completed=False,
            completion_time_sec=None,
            error_count=0,
            comments="",
            recorded_by_user=None,
            recorded_by_role=None,
            timestamp=None
        ))

    db.commit()


def add_audit_entry_db(db: Session, actor: str, role: str, action_type: str, description: str, metadata: Dict[str, Any]) -> DBAuditEntry:
    """Appends SHA-256 hash-chained audit record to SQLite database."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = db.query(DBAuditEntry).count()
    entry_id = f"AUD-{count + 5001}"

    last_entry = db.query(DBAuditEntry).order_by(DBAuditEntry.id.desc()).first()
    prev_hash = last_entry.record_hash if last_entry else GENESIS_HASH

    rec_hash = compute_audit_hash(entry_id, now, actor, role, action_type, description, metadata, prev_hash)
    db_entry = DBAuditEntry(
        id=entry_id,
        timestamp=now,
        actor=actor,
        role=role,
        action_type=action_type,
        description=description,
        metadata_json=json.dumps(metadata),
        previous_hash=prev_hash,
        record_hash=rec_hash
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


def get_workspace_state_db(db: Session) -> ShiftHandoverWorkspace:
    """Retrieves current workspace state directly from SQLite database."""
    ws_row = db.query(DBIncidentWorkspace).filter(DBIncidentWorkspace.id == "INC-9042").first()
    if not ws_row:
        seed_database_from_fixtures(db)
        ws_row = db.query(DBIncidentWorkspace).filter(DBIncidentWorkspace.id == "INC-9042").first()

    # Hydrate Hypotheses
    hypo_rows = db.query(DBHypothesis).all()
    hypotheses: List[Hypothesis] = []
    for h in hypo_rows:
        hypotheses.append(Hypothesis(
            id=h.id,
            title=h.title,
            description=h.description,
            status=HypothesisStatus(h.status),
            confidence_score=h.confidence_score,
            created_by=h.created_by,
            created_at=h.created_at,
            updated_at=h.updated_at,
            evidence_ids=json.loads(h.evidence_ids_json)
        ))

    # Hydrate Evidence
    evid_rows = db.query(DBEvidence).all()
    evidence_list: List[Evidence] = []
    for e in evid_rows:
        evidence_list.append(Evidence(
            id=e.id,
            hypothesis_id=e.hypothesis_id,
            source_type=SourceType(e.source_type),
            source_id=e.source_id,
            title=e.title,
            snippet=e.snippet,
            impact=EvidenceImpact(e.impact),
            added_by=e.added_by,
            added_at=e.added_at
        ))

    # Hydrate Unresolved Actions
    act_rows = db.query(DBActionLog).filter(DBActionLog.status.in_(["PENDING_REVIEW", "APPROVED"])).all()
    unresolved_actions: List[ActionLog] = []
    for a in act_rows:
        unresolved_actions.append(ActionLog(
            id=a.id,
            timestamp=a.timestamp,
            actor=a.actor,
            action_name=a.action_name,
            description=a.description,
            target_component=a.target_component,
            impact_level=ImpactLevel(a.impact_level),
            status=ActionStatus(a.status),
            is_reversible=a.is_reversible,
            requires_two_person_review=a.requires_two_person_review,
            executed_at=a.executed_at,
            approved_by=a.approved_by,
            approver_1=a.approver_1,
            approver_2=a.approver_2,
            rollback_action_id=a.rollback_action_id,
            rollback_executed_at=a.rollback_executed_at,
            rollback_by=a.rollback_by,
            rollback_reason=a.rollback_reason,
            before_state=json.loads(a.before_state_json),
            after_state=json.loads(a.after_state_json),
            rollback_state=json.loads(a.rollback_state_json),
            details=json.loads(a.details_json),
            freshness=FreshnessState(a.freshness)
        ))

    # Hydrate Data Freshness Status
    fresh_row = db.query(DBFreshnessStatus).filter(DBFreshnessStatus.id == 1).first()
    if not fresh_row:
        freshness = DataFreshnessStatus(
            incident_notes=FreshnessState.FRESH,
            chat_excerpts=FreshnessState.FRESH,
            dashboards=FreshnessState.FRESH,
            ownership_changes=FreshnessState.FRESH,
            action_logs=FreshnessState.FRESH,
            last_checked=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    else:
        freshness = DataFreshnessStatus(
            incident_notes=FreshnessState(fresh_row.incident_notes),
            chat_excerpts=FreshnessState(fresh_row.chat_excerpts),
            dashboards=FreshnessState(fresh_row.dashboards),
            ownership_changes=FreshnessState(fresh_row.ownership_changes),
            action_logs=FreshnessState(fresh_row.action_logs),
            last_checked=fresh_row.last_checked
        )

    # Hydrate Source Resilience Items
    res_rows = db.query(DBSourceResilienceItem).all()
    source_resilience: List[SourceResilienceItem] = []
    for r in res_rows:
        source_resilience.append(SourceResilienceItem(
            source_name=r.source_name,
            state=FreshnessState(r.state),
            last_updated=r.last_updated,
            usability=r.usability,
            impact_assessment=r.impact_assessment,
            evidence_count=r.evidence_count
        ))

    # Hydrate Audit Trail
    audit_rows = db.query(DBAuditEntry).all()
    audit_trail: List[AuditEntry] = []
    for aud in audit_rows:
        audit_trail.append(AuditEntry(
            id=aud.id,
            timestamp=aud.timestamp,
            actor=aud.actor,
            role=aud.role,
            action_type=aud.action_type,
            description=aud.description,
            metadata=json.loads(aud.metadata_json),
            previous_hash=aud.previous_hash,
            record_hash=aud.record_hash
        ))

    # Hydrate Change Reviews
    cr_rows = db.query(DBChangeReviewRequest).all()
    change_reviews: List[ChangeReviewRequest] = []
    for cr in cr_rows:
        change_reviews.append(ChangeReviewRequest(
            action_id=cr.action_id,
            action_name=cr.action_name,
            requested_by=cr.requested_by,
            target_component=cr.target_component,
            impact_level=ImpactLevel(cr.impact_level),
            justification=cr.justification,
            proposed_at=cr.proposed_at,
            approved_by=cr.approved_by,
            approver_1=cr.approver_1,
            approver_2=cr.approver_2,
            status=cr.status
        ))

    return ShiftHandoverWorkspace(
        incident_id=ws_row.incident_id,
        incident_title=ws_row.incident_title,
        severity=ws_row.severity,
        started_at=ws_row.started_at,
        outgoing_shift_lead=ws_row.outgoing_shift_lead,
        incoming_shift_lead=ws_row.incoming_shift_lead,
        handover_status=ws_row.handover_status,
        context_loss_risk_score=ws_row.context_loss_risk_score,
        shift_summary=ws_row.shift_summary,
        hypotheses=hypotheses,
        evidence_list=evidence_list,
        unresolved_actions=unresolved_actions,
        freshness=freshness,
        source_resilience=source_resilience,
        audit_trail=audit_trail,
        change_reviews=change_reviews
    )


def get_raw_data_sources_db(db: Session) -> Dict[str, Any]:
    """Retrieves 5 enterprise data sources from SQLite database."""
    notes = [
        IncidentNote(
            id=n.id, timestamp=n.timestamp, author=n.author, severity=n.severity,
            summary=n.summary, tags=json.loads(n.tags_json), content=n.content,
            impacted_apps_count=n.impacted_apps_count, freshness=FreshnessState(n.freshness)
        ) for n in db.query(DBIncidentNote).all()
    ]

    chats = [
        ChatExcerpt(
            id=c.id, timestamp=c.timestamp, channel=c.channel, sender=c.sender,
            sender_role=c.sender_role, text=c.text, key_takeaway=c.key_takeaway,
            tags=json.loads(c.tags_json), freshness=FreshnessState(c.freshness)
        ) for c in db.query(DBChatExcerpt).all()
    ]

    metrics = [
        DashboardMetric(
            id=m.id, name=m.name, category=m.category, current_value=m.current_value,
            unit=m.unit, status=m.status, baseline_value=m.baseline_value,
            threshold_critical=m.threshold_critical, trend=m.trend,
            history=[MetricSeriesPoint(**hp) for hp in json.loads(m.history_json)],
            freshness=FreshnessState(m.freshness)
        ) for m in db.query(DBDashboardMetric).all()
    ]

    ownerships = [
        OwnershipChange(
            id=o.id, timestamp=o.timestamp, previous_lead=o.previous_lead,
            new_lead=o.new_lead, outgoing_shift=o.outgoing_shift,
            incoming_shift=o.incoming_shift, team=o.team, handover_type=o.handover_type,
            notes=o.notes, freshness=FreshnessState(o.freshness)
        ) for o in db.query(DBOwnershipChange).all()
    ]

    actions = [
        ActionLog(
            id=a.id, timestamp=a.timestamp, actor=a.actor, action_name=a.action_name,
            description=a.description, target_component=a.target_component,
            impact_level=ImpactLevel(a.impact_level), status=ActionStatus(a.status),
            is_reversible=a.is_reversible, requires_two_person_review=a.requires_two_person_review,
            executed_at=a.executed_at, approved_by=a.approved_by, approver_1=a.approver_1,
            approver_2=a.approver_2, rollback_action_id=a.rollback_action_id,
            rollback_executed_at=a.rollback_executed_at, rollback_by=a.rollback_by,
            rollback_reason=a.rollback_reason, before_state=json.loads(a.before_state_json),
            after_state=json.loads(a.after_state_json), rollback_state=json.loads(a.rollback_state_json),
            details=json.loads(a.details_json), freshness=FreshnessState(a.freshness)
        ) for a in db.query(DBActionLog).all()
    ]

    return {
        "incident_notes": notes,
        "chat_excerpts": chats,
        "dashboard_metrics": metrics,
        "ownership_changes": ownerships,
        "action_logs": actions
    }


def toggle_source_freshness_db(db: Session, source_name: str, state: FreshnessState, actor: str, role: str) -> Dict[str, Any]:
    """Toggles data source freshness state in SQLite DB and logs audit event."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    fresh_row = db.query(DBFreshnessStatus).filter(DBFreshnessStatus.id == 1).first()
    if not fresh_row:
        fresh_row = DBFreshnessStatus(id=1, last_checked=now)
        db.add(fresh_row)

    if hasattr(fresh_row, source_name):
        setattr(fresh_row, source_name, state.value)
        fresh_row.last_checked = now

        target_display_name = SOURCE_EXPLICIT_MAP.get(source_name)
        res_row = db.query(DBSourceResilienceItem).filter(DBSourceResilienceItem.source_name == target_display_name).first()
        if res_row:
            res_row.state = state.value
            res_row.last_updated = now
            if state == FreshnessState.FRESH:
                res_row.usability = "FULL"
                res_row.impact_assessment = "Source operational; evidence linking intact."
            elif state == FreshnessState.DELAYED:
                res_row.usability = "DEGRADED (15m lag)"
                res_row.impact_assessment = "Data delayed; verify timestamps before executing changes."
            elif state == FreshnessState.STALE:
                res_row.usability = "STALE (>30m lag)"
                res_row.impact_assessment = "Data stale; confidence scores adjusted downward."
            elif state == FreshnessState.MISSING:
                res_row.usability = "UNAVAILABLE"
                res_row.impact_assessment = "Source offline. Workspace operating in resilient graph mode."

        add_audit_entry_db(
            db, actor=actor, role=role, action_type="DATA_SOURCE_CHANGED",
            description=f"Toggled data source `{source_name}` status to `{state.value}`",
            metadata={"source": source_name, "new_state": state.value}
        )
        db.commit()

        updated_freshness = DataFreshnessStatus(
            incident_notes=FreshnessState(fresh_row.incident_notes),
            chat_excerpts=FreshnessState(fresh_row.chat_excerpts),
            dashboards=FreshnessState(fresh_row.dashboards),
            ownership_changes=FreshnessState(fresh_row.ownership_changes),
            action_logs=FreshnessState(fresh_row.action_logs),
            last_checked=fresh_row.last_checked
        )
        return {"status": "SUCCESS", "source": source_name, "new_state": state.value, "freshness": updated_freshness.model_dump()}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {source_name}")


def create_hypothesis_db(db: Session, title: str, description: str, confidence_score: float, actor: str, role: str) -> Dict[str, Any]:
    """Creates a new hypothesis record in SQLite DB."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = db.query(DBHypothesis).count()
    hypo_id = f"HYPO-{count + 1:02d}"

    db_hypo = DBHypothesis(
        id=hypo_id,
        title=title,
        description=description,
        status="INVESTIGATING",
        confidence_score=confidence_score,
        created_by=actor,
        created_at=now,
        updated_at=now,
        evidence_ids_json="[]"
    )
    db.add(db_hypo)

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="HYPOTHESIS_CREATED",
        description=f"Created hypothesis `{hypo_id}`: {title}",
        metadata={"hypothesis_id": hypo_id}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "hypothesis": {
            "id": hypo_id, "title": title, "description": description,
            "status": "INVESTIGATING", "confidence_score": confidence_score,
            "created_by": actor, "created_at": now, "updated_at": now, "evidence_ids": []
        }
    }


def link_evidence_db(db: Session, hypothesis_id: str, source_type: SourceType, source_id: str, title: str, snippet: str, impact: EvidenceImpact, actor: str, role: str) -> Dict[str, Any]:
    """Links an evidence item to a hypothesis in SQLite DB."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    hypo_db = db.query(DBHypothesis).filter(DBHypothesis.id == hypothesis_id).first()
    if not hypo_db:
        raise HTTPException(status_code=404, detail=f"Hypothesis '{hypothesis_id}' not found")

    count = db.query(DBEvidence).count()
    evid_id = f"EVID-{count + 1:02d}"

    db_evid = DBEvidence(
        id=evid_id,
        hypothesis_id=hypothesis_id,
        source_type=source_type.value,
        source_id=source_id,
        title=title,
        snippet=snippet,
        impact=impact.value,
        added_by=actor,
        added_at=now
    )
    db.add(db_evid)

    evid_ids = json.loads(hypo_db.evidence_ids_json)
    evid_ids.append(evid_id)
    hypo_db.evidence_ids_json = json.dumps(evid_ids)

    if impact == EvidenceImpact.SUPPORTS:
        hypo_db.confidence_score = min(0.99, hypo_db.confidence_score + 0.15)
    elif impact == EvidenceImpact.REFUTES:
        hypo_db.confidence_score = max(0.01, hypo_db.confidence_score - 0.25)
        if hypo_db.confidence_score < 0.1:
            hypo_db.status = "DISPROVED"

    hypo_db.updated_at = now

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="EVIDENCE_LINKED",
        description=f"Linked evidence `{evid_id}` to Hypothesis `{hypothesis_id}` ({impact.value})",
        metadata={"evidence_id": evid_id, "hypothesis_id": hypothesis_id, "source_id": source_id}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "evidence": {
            "id": evid_id, "hypothesis_id": hypothesis_id, "source_type": source_type.value,
            "source_id": source_id, "title": title, "snippet": snippet, "impact": impact.value,
            "added_by": actor, "added_at": now
        },
        "updated_hypothesis": {
            "id": hypo_db.id, "title": hypo_db.title, "description": hypo_db.description,
            "status": hypo_db.status, "confidence_score": hypo_db.confidence_score,
            "created_by": hypo_db.created_by, "created_at": hypo_db.created_at,
            "updated_at": hypo_db.updated_at, "evidence_ids": json.loads(hypo_db.evidence_ids_json)
        }
    }


def approve_change_review_db(db: Session, action_id: str, actor: str, role: str) -> Dict[str, Any]:
    """Applies two-person dual approval state machine to DB records."""
    req_db = db.query(DBChangeReviewRequest).filter(DBChangeReviewRequest.action_id == action_id).first()
    if not req_db:
        raise HTTPException(status_code=404, detail=f"Change review request for action '{action_id}' not found")

    if req_db.approver_1 and req_db.approver_1.lower() == actor.lower():
        raise HTTPException(status_code=400, detail=f"Dual Approval Failure: User '{actor}' has already provided Approval 1. Approval 2 requires a distinct second user.")

    if not req_db.approver_1:
        req_db.approver_1 = actor
        req_db.status = "PENDING_APPROVAL_2"
    else:
        req_db.approver_2 = actor
        req_db.approved_by = f"{req_db.approver_1} & {req_db.approver_2}"
        req_db.status = "APPROVED"

    act_db = db.query(DBActionLog).filter(DBActionLog.id == action_id).first()
    if act_db:
        act_db.approver_1 = req_db.approver_1
        act_db.approver_2 = req_db.approver_2
        act_db.approved_by = req_db.approved_by
        if req_db.status == "APPROVED":
            act_db.status = "APPROVED"

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="CHANGE_REVIEW_APPROVED",
        description=f"Approved change review step for action `{action_id}` ({req_db.status})",
        metadata={"action_id": action_id, "approver": actor, "review_status": req_db.status}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "change_review": {
            "action_id": req_db.action_id, "action_name": req_db.action_name,
            "requested_by": req_db.requested_by, "target_component": req_db.target_component,
            "impact_level": req_db.impact_level, "justification": req_db.justification,
            "proposed_at": req_db.proposed_at, "approved_by": req_db.approved_by,
            "approver_1": req_db.approver_1, "approver_2": req_db.approver_2, "status": req_db.status
        }
    }


def execute_action_db(db: Session, action_id: str, actor: str, role: str) -> Dict[str, Any]:
    """Executes action in DB, capturing dynamic before_state snapshot and applying after_state."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act_db = db.query(DBActionLog).filter(DBActionLog.id == action_id).first()
    if not act_db:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")

    if act_db.status == "EXECUTED":
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been executed")

    if act_db.requires_two_person_review and act_db.status != "APPROVED":
        add_audit_entry_db(
            db, actor=actor, role=role, action_type="UNAUTHORIZED_ACTION_ATTEMPT",
            description=f"Blocked unapproved execution attempt for action `{action_id}`",
            metadata={"action_id": action_id}
        )
        raise HTTPException(status_code=403, detail="Forbidden: High-impact action requires complete 2-person approval before execution")

    # Capture before_state dynamically from DB dashboard metrics
    metrics_db = db.query(DBDashboardMetric).all()
    before_state = {}
    for m in metrics_db:
        if m.id == "METRIC-AUTH-02":
            before_state["jwt_error_rate_percent"] = m.current_value
        elif m.id == "METRIC-AUTH-03":
            before_state["stale_cache_ratio_percent"] = m.current_value

    after_state = {"jwt_error_rate_percent": 0.02, "stale_cache_ratio_percent": 0.0}

    act_db.before_state_json = json.dumps(before_state)
    act_db.after_state_json = json.dumps(after_state)
    act_db.status = "EXECUTED"
    act_db.executed_at = now

    # Apply after_state to metrics in DB
    for m in metrics_db:
        if m.id == "METRIC-AUTH-02":
            m.current_value = after_state["jwt_error_rate_percent"]
            m.status = "NORMAL"
            m.trend = "FALLING"
        elif m.id == "METRIC-AUTH-03":
            m.current_value = after_state["stale_cache_ratio_percent"]
            m.status = "NORMAL"
            m.trend = "FALLING"

    ws_db = db.query(DBIncidentWorkspace).filter(DBIncidentWorkspace.id == "INC-9042").first()
    if ws_db:
        ws_db.context_loss_risk_score = 2.1
        ws_db.shift_summary += " [EXECUTION SUCCESS: API Edge Gateway cache flushed. JWT error rate reduced to 0.02%. Incident resolved.]"

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="ACTION_EXECUTED",
        description=f"Executed action `{action_id}`: {act_db.action_name}",
        metadata={"action_id": action_id, "before_state": before_state, "after_state": after_state}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "action": {
            "id": act_db.id, "action_name": act_db.action_name, "status": act_db.status,
            "executed_at": act_db.executed_at, "before_state": before_state, "after_state": after_state
        },
        "workspace_risk_score": 2.1
    }


def rollback_action_db(db: Session, action_id: str, rationale: str, actor: str, role: str) -> Dict[str, Any]:
    """Rolls back action in DB, reading before_state snapshot and physically restoring system metrics."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    act_db = db.query(DBActionLog).filter(DBActionLog.id == action_id).first()
    if not act_db:
        raise HTTPException(status_code=404, detail=f"Action log entry '{action_id}' not found")

    if not act_db.is_reversible:
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' is marked NON-REVERSIBLE and cannot be rolled back")

    if act_db.status == "ROLLED_BACK":
        raise HTTPException(status_code=400, detail=f"Action '{action_id}' has already been rolled back")

    if act_db.status != "EXECUTED":
        raise HTTPException(status_code=400, detail=f"Cannot rollback action '{action_id}' because it has not been executed yet (Current Status: {act_db.status})")

    before_state = json.loads(act_db.before_state_json)

    act_db.status = "ROLLED_BACK"
    act_db.rollback_executed_at = now
    act_db.rollback_by = actor
    act_db.rollback_reason = rationale
    act_db.rollback_state_json = json.dumps(before_state)

    # Restore metric values from before_state snapshot
    restored_err = before_state.get("jwt_error_rate_percent", 18.6)
    restored_stale = before_state.get("stale_cache_ratio_percent", 42.5)

    metrics_db = db.query(DBDashboardMetric).all()
    for m in metrics_db:
        if m.id == "METRIC-AUTH-02":
            m.current_value = restored_err
            m.status = "CRITICAL" if restored_err > 5.0 else "NORMAL"
            m.trend = "RISING"
        elif m.id == "METRIC-AUTH-03":
            m.current_value = restored_stale
            m.status = "CRITICAL" if restored_stale > 1.0 else "NORMAL"
            m.trend = "HIGH_STABLE"

    ws_db = db.query(DBIncidentWorkspace).filter(DBIncidentWorkspace.id == "INC-9042").first()
    if ws_db:
        ws_db.context_loss_risk_score = 12.4

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="ACTION_ROLLED_BACK",
        description=f"Executed rollback for action `{action_id}` ({act_db.action_name}). Rationale: {rationale}",
        metadata={"action_id": action_id, "restored_state": before_state, "rationale": rationale}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "action": {
            "id": act_db.id, "action_name": act_db.action_name, "status": act_db.status,
            "rollback_executed_at": act_db.rollback_executed_at, "rollback_by": act_db.rollback_by,
            "rollback_reason": act_db.rollback_reason, "restored_state": before_state
        }
    }


def verify_audit_trail_db(db: Session) -> AuditVerificationResult:
    """Verifies SHA-256 hash chain integrity of audit records in SQLite database."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    audit_rows = db.query(DBAuditEntry).order_by(DBAuditEntry.id.asc()).all()

    if not audit_rows:
        return AuditVerificationResult(valid=True, records_checked=0, first_invalid_record=None, timestamp=now)

    prev_hash = GENESIS_HASH
    for idx, entry in enumerate(audit_rows):
        computed = compute_audit_hash(
            entry.id, entry.timestamp, entry.actor, entry.role,
            entry.action_type, entry.description, json.loads(entry.metadata_json), entry.previous_hash
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
        records_checked=len(audit_rows),
        first_invalid_record=None,
        timestamp=now
    )


def tamper_test_db(db: Session, record_index: int, actor: str, role: str) -> Dict[str, Any]:
    """Tampers with an audit record in SQLite DB to demonstrate tamper detection."""
    audit_rows = db.query(DBAuditEntry).order_by(DBAuditEntry.id.asc()).all()
    if not audit_rows or record_index >= len(audit_rows):
        raise HTTPException(status_code=400, detail="Invalid audit record index")

    target_entry = audit_rows[record_index]
    target_entry.description += " [TAMPERED BY TEST ENGINE]"
    db.commit()

    return {"status": "SUCCESS", "message": f"Tampered DB record index {record_index} (ID: {target_entry.id})"}


def signoff_handover_db(db: Session, outgoing_user: str, incoming_user: str, notes: str, actor: str, role: str) -> Dict[str, Any]:
    """Updates formal shift handover signoff in SQLite DB."""
    out_clean = outgoing_user.strip()
    in_clean = incoming_user.strip()

    if not out_clean or not in_clean:
        raise HTTPException(status_code=400, detail="Handover Sign-off Error: Both outgoing and incoming shift lead identities are required")

    if out_clean.lower() == in_clean.lower():
        raise HTTPException(status_code=400, detail=f"Handover Sign-off Error: Outgoing user '{out_clean}' and Incoming user '{in_clean}' cannot be identical")

    ws_db = db.query(DBIncidentWorkspace).filter(DBIncidentWorkspace.id == "INC-9042").first()
    if ws_db:
        ws_db.outgoing_shift_lead = out_clean
        ws_db.incoming_shift_lead = in_clean
        ws_db.handover_status = "ACCEPTED"

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="HANDOVER_ACCEPTED",
        description=f"Formal Shift Handover ACCEPTED between Outgoing: '{out_clean}' and Incoming: '{in_clean}'.",
        metadata={"outgoing_user": out_clean, "incoming_user": in_clean, "notes": notes}
    )
    db.commit()

    return {"status": "SUCCESS", "handover_status": "ACCEPTED", "outgoing_user": out_clean, "incoming_user": in_clean}


def get_stakeholder_validation_db(db: Session) -> Dict[str, Any]:
    """Retrieves stakeholder tasks and summary statistics from SQLite DB."""
    tasks_db = db.query(DBStakeholderTask).all()
    tasks: List[Dict[str, Any]] = []

    for t in tasks_db:
        tasks.append({
            "task_id": t.task_id,
            "task_name": t.task_name,
            "validation_status": t.validation_status,
            "completed": t.completed,
            "completion_time_sec": t.completion_time_sec,
            "error_count": t.error_count,
            "comments": t.comments,
            "recorded_by_user": t.recorded_by_user,
            "recorded_by_role": t.recorded_by_role,
            "timestamp": t.timestamp
        })

    observed = [t for t in tasks_db if t.validation_status == ValidationCategory.OBSERVED_VALIDATION.value and t.completed]
    avg_time = sum(t.completion_time_sec for t in observed if t.completion_time_sec) / len(observed) if observed else 0.0
    total_errors = sum(t.error_count for t in observed)

    not_tested = sum(1 for t in tasks_db if t.validation_status == ValidationCategory.NOT_TESTED.value)
    demo_sample = sum(1 for t in tasks_db if t.validation_status == ValidationCategory.DEMO_SAMPLE.value)

    summary = ValidationSummary(
        total_tasks=len(tasks_db),
        not_tested_count=not_tested,
        demo_sample_count=demo_sample,
        observed_validation_count=len(observed),
        observed_completion_rate_percent=round((len(observed) / len(tasks_db)) * 100.0, 1) if tasks_db else 0.0,
        observed_avg_task_time_sec=round(avg_time, 1),
        observed_total_errors=total_errors,
        most_difficult_task="TASK-03 (Finding supporting evidence snippet)"
    )

    return {"tasks": tasks, "summary": summary.model_dump()}


def record_stakeholder_task_db(db: Session, task_id: str, completed: bool, completion_time_sec: Optional[float], error_count: int, comments: str, validation_status: ValidationCategory, actor: str, role: str) -> Dict[str, Any]:
    """Records an observational stakeholder validation task in SQLite DB."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    task_db = db.query(DBStakeholderTask).filter(DBStakeholderTask.task_id == task_id).first()
    if not task_db:
        raise HTTPException(status_code=404, detail=f"Validation task '{task_id}' not found")

    task_db.validation_status = validation_status.value
    task_db.completed = completed
    task_db.completion_time_sec = completion_time_sec
    task_db.error_count = error_count
    task_db.comments = comments
    task_db.recorded_by_user = actor
    task_db.recorded_by_role = role
    task_db.timestamp = now

    add_audit_entry_db(
        db, actor=actor, role=role, action_type="STAKEHOLDER_VALIDATION_RECORDED",
        description=f"Recorded stakeholder validation task `{task_id}` status: {validation_status.value}",
        metadata={"task_id": task_id, "validation_status": validation_status.value}
    )
    db.commit()

    return {
        "status": "SUCCESS",
        "task": {
            "task_id": task_db.task_id, "task_name": task_db.task_name,
            "validation_status": task_db.validation_status, "completed": task_db.completed,
            "completion_time_sec": task_db.completion_time_sec, "error_count": task_db.error_count,
            "comments": task_db.comments, "recorded_by_user": task_db.recorded_by_user,
            "recorded_by_role": task_db.recorded_by_role, "timestamp": task_db.timestamp
        }
    }


def toggle_stakeholder_demo_db(db: Session, mode: str) -> Dict[str, Any]:
    """Toggles stakeholder tasks between NOT_TESTED and DEMO_SAMPLE in SQLite DB."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tasks_db = db.query(DBStakeholderTask).all()

    for t in tasks_db:
        if mode == "DEMO_SAMPLE":
            t.validation_status = "DEMO_SAMPLE"
            t.completed = True
            t.completion_time_sec = 15.0
            t.error_count = 0
            t.comments = "Illustrative Demo Sample Data — Not Actual User Study Results"
            t.recorded_by_user = "Demo Evaluator"
            t.recorded_by_role = "Enterprise App Developer / Stakeholder"
            t.timestamp = now
        else:
            t.validation_status = "NOT_TESTED"
            t.completed = False
            t.completion_time_sec = None
            t.error_count = 0
            t.comments = ""
            t.recorded_by_user = None
            t.recorded_by_role = None
            t.timestamp = None

    db.commit()
    return get_stakeholder_validation_db(db)
