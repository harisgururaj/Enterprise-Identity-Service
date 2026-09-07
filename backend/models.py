"""
Data models for Enterprise Identity Service Shift-Handover Workspace.
Defines schemas for Data Sources, Hypotheses, Evidence, Action Logs,
Change Review, Hash-Chained Audit Trail, Benchmark Metrics, Resilience Experiments,
Demo User Identity, and Stakeholder Validation Tasks.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FreshnessState(str, Enum):
    FRESH = "FRESH"          # Data updated < 2 mins ago
    DELAYED = "DELAYED"      # Data updated 2-10 mins ago
    STALE = "STALE"          # Data updated > 10 mins ago
    MISSING = "MISSING"      # Data source unreachable or disconnected


class ImpactLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class HypothesisStatus(str, Enum):
    INVESTIGATING = "INVESTIGATING"
    CONFIRMED = "CONFIRMED"
    DISPROVED = "DISPROVED"
    SUPERSEDED = "SUPERSEDED"


class EvidenceImpact(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    NEUTRAL = "NEUTRAL"


class SourceType(str, Enum):
    CHAT = "CHAT"
    METRIC = "METRIC"
    ACTION_LOG = "ACTION_LOG"
    INCIDENT_NOTE = "INCIDENT_NOTE"
    OWNERSHIP_LOG = "OWNERSHIP_LOG"


class ActionStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    ROLLED_BACK = "ROLLED_BACK"
    REJECTED = "REJECTED"


class UserRole(str, Enum):
    SRE_ENGINEER = "SRE / On-Call Specialist"
    INCIDENT_COMMANDER = "Incident Commander / Handover Lead"
    APP_DEVELOPER = "Enterprise App Developer / Stakeholder"


class ValidationCategory(str, Enum):
    NOT_TESTED = "NOT_TESTED"
    DEMO_SAMPLE = "DEMO_SAMPLE"
    OBSERVED_VALIDATION = "OBSERVED_VALIDATION"


class AuthUserIdentity(BaseModel):
    """Prototype Demo Authenticated User Identity Context."""
    username: str
    role: str


# --- Data Source Models ---

class IncidentNote(BaseModel):
    id: str
    timestamp: str
    author: str
    severity: str
    summary: str
    tags: List[str]
    content: str
    impacted_apps_count: int = 480
    freshness: FreshnessState = FreshnessState.FRESH


class ChatExcerpt(BaseModel):
    id: str
    timestamp: str
    channel: str
    sender: str
    sender_role: str
    text: str
    key_takeaway: Optional[str] = None
    tags: List[str] = []
    freshness: FreshnessState = FreshnessState.FRESH


class MetricSeriesPoint(BaseModel):
    time: str
    value: float


class DashboardMetric(BaseModel):
    id: str
    name: str
    category: str
    current_value: float
    unit: str
    status: str  # NORMAL, WARNING, CRITICAL
    baseline_value: float
    threshold_critical: float
    trend: str  # RISING, FALLING, STABLE
    history: List[MetricSeriesPoint]
    freshness: FreshnessState = FreshnessState.FRESH


class OwnershipChange(BaseModel):
    id: str
    timestamp: str
    previous_lead: str
    new_lead: str
    outgoing_shift: str
    incoming_shift: str
    team: str
    handover_type: str  # ROUTINE, EMERGENCY, ESCALATION
    notes: str
    freshness: FreshnessState = FreshnessState.FRESH


class ActionLog(BaseModel):
    id: str
    timestamp: str
    actor: str
    action_name: str
    description: str
    target_component: str
    impact_level: ImpactLevel
    status: ActionStatus
    is_reversible: bool
    requires_two_person_review: bool
    executed_at: Optional[str] = None
    approved_by: Optional[str] = None
    approver_1: Optional[str] = None
    approver_2: Optional[str] = None
    rollback_action_id: Optional[str] = None
    rollback_executed_at: Optional[str] = None
    rollback_by: Optional[str] = None
    rollback_reason: Optional[str] = None
    before_state: Dict[str, Any] = {}
    after_state: Dict[str, Any] = {}
    rollback_state: Dict[str, Any] = {}
    details: Dict[str, Any] = {}
    freshness: FreshnessState = FreshnessState.FRESH


# --- Hypothesis & Evidence Models ---

class Evidence(BaseModel):
    id: str
    hypothesis_id: str
    source_type: SourceType
    source_id: str
    title: str
    snippet: str
    impact: EvidenceImpact
    added_by: str
    added_at: str


class Hypothesis(BaseModel):
    id: str
    title: str
    description: str
    status: HypothesisStatus
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    created_by: str
    created_at: str
    updated_at: str
    evidence_ids: List[str] = []


# --- Shift Handover & Audit Models ---

class AuditEntry(BaseModel):
    id: str
    timestamp: str
    actor: str
    role: str
    action_type: str
    description: str
    metadata: Dict[str, Any] = {}
    previous_hash: str = ""
    record_hash: str = ""


class AuditVerificationResult(BaseModel):
    valid: bool
    records_checked: int
    first_invalid_record: Optional[str] = None
    timestamp: str


class DataFreshnessStatus(BaseModel):
    incident_notes: FreshnessState
    chat_excerpts: FreshnessState
    dashboards: FreshnessState
    ownership_changes: FreshnessState
    action_logs: FreshnessState
    last_checked: str


class ChangeReviewRequest(BaseModel):
    action_id: str
    action_name: str
    requested_by: str
    target_component: str
    impact_level: ImpactLevel
    justification: str
    proposed_at: str
    approved_by: Optional[str] = None
    approver_1: Optional[str] = None
    approver_2: Optional[str] = None
    status: str = "PENDING_APPROVAL"


class SourceResilienceItem(BaseModel):
    source_name: str
    state: FreshnessState
    last_updated: str
    usability: str
    impact_assessment: str
    evidence_count: int


class ShiftHandoverWorkspace(BaseModel):
    incident_id: str
    incident_title: str
    severity: str
    started_at: str
    outgoing_shift_lead: str
    incoming_shift_lead: str
    handover_status: str  # IN_REVIEW, ACCEPTED
    context_loss_risk_score: float  # 0 to 100
    shift_summary: str
    hypotheses: List[Hypothesis]
    evidence_list: List[Evidence]
    unresolved_actions: List[ActionLog]
    freshness: DataFreshnessStatus
    source_resilience: List[SourceResilienceItem] = []
    audit_trail: List[AuditEntry]
    change_reviews: List[ChangeReviewRequest]


# --- Evaluation & Validation Models ---

class BenchmarkResult(BaseModel):
    evaluation_label: str = "Controlled simulated evaluation using reproducible incident scenarios"
    trials_count: int
    seed: int
    baseline_handover_delay_minutes: float
    solution_handover_delay_minutes: float
    delay_reduction_minutes: float
    percentage_reduction: float
    target_reduction_percent: float = 25.0
    pass_target_evaluation: bool = True
    baseline_std_dev: float
    solution_std_dev: float
    confidence_interval_95: str
    baseline_mttr_minutes: float
    solution_mttr_minutes: float
    mttr_reduction_percent: float
    baseline_rework_rate_percent: float
    solution_rework_rate_percent: float
    error_analysis: str


class ResilienceConditionResult(BaseModel):
    condition_id: str
    condition_name: str
    chat_state: FreshnessState
    trials_count: int
    mean_recovery_delay_minutes: float
    std_dev_minutes: float
    task_success_rate_percent: float
    degradation_vs_fresh_minutes: float
    critical_evidence_available: bool
    status: str  # OPERATIONAL, DEGRADED


class ResilienceExperimentSummary(BaseModel):
    experiment_label: str = "Controlled Simulated Resilience Experiment"
    seed: int
    trials_per_condition: int
    conditions: List[ResilienceConditionResult]


class StakeholderValidationTask(BaseModel):
    task_id: str
    task_name: str
    validation_status: ValidationCategory = ValidationCategory.NOT_TESTED
    completed: bool = False
    completion_time_sec: Optional[float] = None
    error_count: int = 0
    comments: str = ""
    recorded_by_user: Optional[str] = None
    recorded_by_role: Optional[str] = None
    timestamp: Optional[str] = None


class ValidationSummary(BaseModel):
    total_tasks: int
    not_tested_count: int
    demo_sample_count: int
    observed_validation_count: int
    observed_completion_rate_percent: float
    observed_avg_task_time_sec: float
    observed_total_errors: int
    most_difficult_task: str
