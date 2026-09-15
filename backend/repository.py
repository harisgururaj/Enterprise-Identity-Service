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
