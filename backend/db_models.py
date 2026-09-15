"""
SQLAlchemy ORM Data Models for Persistent Storage in SQLite Database.
Defines tables for Workspace, 5 Enterprise Sources, Hypotheses, Evidence, Actions,
Change Reviews, SHA-256 Hash-Chained Audit Trail, and Stakeholder Validation Tasks.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, Text
from backend.database import Base


class DBIncidentWorkspace(Base):
    __tablename__ = "incident_workspace"

    id = Column(String(50), primary_key=True, default="INC-9042")
    incident_id = Column(String(50), nullable=False)
    incident_title = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=False)
    started_at = Column(String(50), nullable=False)
    outgoing_shift_lead = Column(String(100), nullable=False)
    incoming_shift_lead = Column(String(100), nullable=False)
    handover_status = Column(String(50), nullable=False, default="IN_REVIEW")
    context_loss_risk_score = Column(Float, nullable=False, default=12.4)
    shift_summary = Column(Text, nullable=False)


class DBIncidentNote(Base):
    __tablename__ = "incident_notes"

    id = Column(String(50), primary_key=True)
    timestamp = Column(String(50), nullable=False)
    author = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    summary = Column(String(255), nullable=False)
    tags_json = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    impacted_apps_count = Column(Integer, default=480)
    freshness = Column(String(20), nullable=False, default="FRESH")


class DBChatExcerpt(Base):
    __tablename__ = "chat_excerpts"

    id = Column(String(50), primary_key=True)
    timestamp = Column(String(50), nullable=False)
    channel = Column(String(100), nullable=False)
    sender = Column(String(100), nullable=False)
    sender_role = Column(String(100), nullable=False)
    text = Column(Text, nullable=False)
    key_takeaway = Column(Text, nullable=True)
    tags_json = Column(Text, nullable=False, default="[]")
    freshness = Column(String(20), nullable=False, default="FRESH")


class DBDashboardMetric(Base):
    __tablename__ = "dashboard_metrics"

    id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    current_value = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    baseline_value = Column(Float, nullable=False)
    threshold_critical = Column(Float, nullable=False)
    trend = Column(String(20), nullable=False)
    history_json = Column(Text, nullable=False, default="[]")
    freshness = Column(String(20), nullable=False, default="FRESH")


class DBOwnershipChange(Base):
    __tablename__ = "ownership_changes"

    id = Column(String(50), primary_key=True)
    timestamp = Column(String(50), nullable=False)
    previous_lead = Column(String(100), nullable=False)
    new_lead = Column(String(100), nullable=False)
    outgoing_shift = Column(String(100), nullable=False)
    incoming_shift = Column(String(100), nullable=False)
    team = Column(String(100), nullable=False)
    handover_type = Column(String(50), nullable=False)
    notes = Column(Text, nullable=False)
    freshness = Column(String(20), nullable=False, default="FRESH")


class DBActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(String(50), primary_key=True)
    timestamp = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    action_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_component = Column(String(100), nullable=False)
    impact_level = Column(String(20), nullable=False)
    status = Column(String(50), nullable=False)
    is_reversible = Column(Boolean, nullable=False, default=True)
    requires_two_person_review = Column(Boolean, nullable=False, default=True)
    executed_at = Column(String(50), nullable=True)
    approved_by = Column(String(200), nullable=True)
    approver_1 = Column(String(100), nullable=True)
    approver_2 = Column(String(100), nullable=True)
    rollback_action_id = Column(String(50), nullable=True)
    rollback_executed_at = Column(String(50), nullable=True)
    rollback_by = Column(String(100), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    before_state_json = Column(Text, nullable=False, default="{}")
    after_state_json = Column(Text, nullable=False, default="{}")
    rollback_state_json = Column(Text, nullable=False, default="{}")
    details_json = Column(Text, nullable=False, default="{}")
    freshness = Column(String(20), nullable=False, default="FRESH")


class DBHypothesis(Base):
    __tablename__ = "hypotheses"

    id = Column(String(50), primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(50), nullable=False)
    confidence_score = Column(Float, nullable=False)
    created_by = Column(String(100), nullable=False)
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)
    evidence_ids_json = Column(Text, nullable=False, default="[]")


class DBEvidence(Base):
    __tablename__ = "evidence"

    id = Column(String(50), primary_key=True)
    hypothesis_id = Column(String(50), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_id = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    snippet = Column(Text, nullable=False)
    impact = Column(String(20), nullable=False)
    added_by = Column(String(100), nullable=False)
    added_at = Column(String(50), nullable=False)


class DBChangeReviewRequest(Base):
    __tablename__ = "change_reviews"

    action_id = Column(String(50), primary_key=True)
    action_name = Column(String(255), nullable=False)
    requested_by = Column(String(100), nullable=False)
    target_component = Column(String(100), nullable=False)
    impact_level = Column(String(20), nullable=False)
    justification = Column(Text, nullable=False)
    proposed_at = Column(String(50), nullable=False)
    approved_by = Column(String(200), nullable=True)
    approver_1 = Column(String(100), nullable=True)
    approver_2 = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, default="PENDING_APPROVAL")


class DBSourceResilienceItem(Base):
    __tablename__ = "source_resilience"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False, unique=True)
    state = Column(String(20), nullable=False, default="FRESH")
    last_updated = Column(String(50), nullable=False)
    usability = Column(String(100), nullable=False)
    impact_assessment = Column(Text, nullable=False)
    evidence_count = Column(Integer, nullable=False, default=0)


class DBAuditEntry(Base):
    __tablename__ = "audit_entries"

    id = Column(String(50), primary_key=True)
    timestamp = Column(String(50), nullable=False)
    actor = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    previous_hash = Column(String(128), nullable=False)
    record_hash = Column(String(128), nullable=False)


class DBFreshnessStatus(Base):
    __tablename__ = "freshness_status"

    id = Column(Integer, primary_key=True, default=1)
    incident_notes = Column(String(20), nullable=False, default="FRESH")
    chat_excerpts = Column(String(20), nullable=False, default="FRESH")
    dashboards = Column(String(20), nullable=False, default="FRESH")
    ownership_changes = Column(String(20), nullable=False, default="FRESH")
    action_logs = Column(String(20), nullable=False, default="FRESH")
    last_checked = Column(String(50), nullable=False)


class DBStakeholderTask(Base):
    __tablename__ = "stakeholder_tasks"

    task_id = Column(String(50), primary_key=True)
    task_name = Column(String(255), nullable=False)
    validation_status = Column(String(50), nullable=False, default="NOT_TESTED")
    completed = Column(Boolean, nullable=False, default=False)
    completion_time_sec = Column(Float, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)
    comments = Column(Text, nullable=False, default="")
    recorded_by_user = Column(String(100), nullable=True)
    recorded_by_role = Column(String(100), nullable=True)
    timestamp = Column(String(50), nullable=True)
