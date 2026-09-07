"""
Data Generator for Enterprise Identity Service Operational Scenario.
Generates realistic data for 5 enterprise sources, hypotheses, evidence graph,
hash-chained audit trail, resilience status, and shift handover state.
"""

from typing import List, Dict, Any
from datetime import datetime, timezone
import hashlib
import json

from backend.models import (
    IncidentNote, ChatExcerpt, DashboardMetric, MetricSeriesPoint,
    OwnershipChange, ActionLog, Hypothesis, Evidence,
    FreshnessState, ImpactLevel, HypothesisStatus, EvidenceImpact,
    SourceType, ActionStatus, AuditEntry, DataFreshnessStatus,
    ChangeReviewRequest, SourceResilienceItem, ShiftHandoverWorkspace
)


GENESIS_HASH = "GENESIS_HASH_0000000000000000000000000000000000000000000000000000000000000000"


def compute_audit_hash(entry_id: str, timestamp: str, actor: str, role: str, action_type: str, description: str, metadata: Dict[str, Any], previous_hash: str) -> str:
    """Computes canonical SHA-256 hash for an audit trail entry."""
    meta_json = json.dumps(metadata, sort_keys=True)
    raw = f"{entry_id}|{timestamp}|{actor}|{role}|{action_type}|{description}|{meta_json}|{previous_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_initial_data_sources() -> Dict[str, Any]:
    """Generates the 5 enterprise data sources for SEV-1 Identity Service incident."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Data Source 1: Incident Notes
    incident_notes = [
        IncidentNote(
            id="NOTE-INC-9042-01",
            timestamp="2026-09-03T07:15:00Z",
            author="Marcus Vance (Shift Lead Alpha)",
            severity="SEV-1",
            summary="OAuth2 Token Generation 500 Spike & Verification Failures across Enterprise Apps",
            tags=["AUTH", "KEY_ROTATION", "REDIS_LEAK", "SEV-1"],
            content=(
                "At 07:10 UTC, automated alerting reported a severe spike in OAuth2 token verification failures (401/500 errors) "
                "across enterprise downstream applications (HR Portal, Payment Gateway, Developer Platform). Initial triage indicated "
                "a Vault key rotation to signing key v4.1 at 07:00 UTC. SRE team attempted rate limit adjustments and Redis session pool "
                "flushes. Handover required due to shift transition at 09:30 UTC."
            ),
            impacted_apps_count=480,
            freshness=FreshnessState.FRESH
        ),
        IncidentNote(
            id="NOTE-INC-9042-02",
            timestamp="2026-09-03T08:45:00Z",
            author="Elena Rostova (Shift Lead Beta - Incoming)",
            severity="SEV-1",
            summary="Pre-Handover Diagnostics & Contradictory Metric Signals",
            tags=["DIAGNOSTICS", "CACHE_MISMATCH", "HANDOVER_PREP"],
            content=(
                "Inspected API Gateway logs. Token issuance by Identity Core pod cluster is succeeding (200 OK), but API Edge Gateways "
                "are rejecting 42% of JWT tokens. Hypothesis H1 (Vault rotation) supported by Gateway key cache TTL (4h). Hypothesis H2 "
                "(Redis memory pressure) refutes direct causation due to pool memory remaining under 45% threshold."
            ),
            impacted_apps_count=480,
            freshness=FreshnessState.FRESH
        )
    ]

    # Data Source 2: Chat Excerpts
    chat_excerpts = [
        ChatExcerpt(
            id="CHAT-8801",
            timestamp="2026-09-03T07:05:12Z",
            channel="#incident-identity-core",
            sender="Marcus Vance",
            sender_role="SRE Lead",
            text="@channel SEV-1 declared. Enterprise Auth Service error rate hit 18.4%. Downstream apps getting HTTP 401 on valid user tokens.",
            key_takeaway="Incident declaration & initial error spike",
            tags=["SEV-1", "ALERT"],
            freshness=FreshnessState.FRESH
        ),
        ChatExcerpt(
            id="CHAT-8804",
            timestamp="2026-09-03T07:18:45Z",
            channel="#incident-identity-core",
            sender="Devon Zhao",
            sender_role="Security Infra Engineer",
            text="Vault auto-rotated identity token signing key `id-jwt-sig-key` from v3.9 -> v4.1 at 07:00:00Z. Rotation status marked SUCCESS in Vault.",
            key_takeaway="Vault key rotation completed at 07:00 UTC",
            tags=["VAULT", "KEY_ROTATION"],
            freshness=FreshnessState.FRESH
        ),
        ChatExcerpt(
            id="CHAT-8812",
            timestamp="2026-09-03T07:42:10Z",
            channel="#incident-identity-core",
            sender="Priya Patel",
            sender_role="Gateway SRE",
            text="Wait, API Edge Gateways cache the JWKS public key set for 4 hours. The edge nodes didn't receive the webhook cache invalidation trigger because edge webhook listener timed out!",
            key_takeaway="Edge Gateways failed to receive JWKS cache invalidation trigger",
            tags=["JWKS", "CACHE_MISMATCH", "GATEWAY"],
            freshness=FreshnessState.FRESH
        ),
        ChatExcerpt(
            id="CHAT-8825",
            timestamp="2026-09-03T08:15:30Z",
            channel="#incident-identity-core",
            sender="Marcus Vance",
            sender_role="SRE Lead",
            text="Tried flushes on Redis session cluster to clear stale tokens, but Redis latency spiked to 240ms due to connection lock contention. Rolling back Redis flush action now.",
            key_takeaway="Redis flush attempt caused latency spike; action rolled back",
            tags=["REDIS", "ACTION_LOG", "ROLLBACK"],
            freshness=FreshnessState.FRESH
        ),
        ChatExcerpt(
            id="CHAT-8839",
            timestamp="2026-09-03T09:10:05Z",
            channel="#incident-identity-core",
            sender="Elena Rostova",
            sender_role="Incoming Shift Lead",
            text="Preparing shift handover sync. We need to confirm if rolling back signing key to v3.9 in Vault vs forcing API Gateway JWKS cache flush is safer.",
            key_takeaway="Handover preparation: Key Rollback vs Cache Flush decision required",
            tags=["HANDOVER", "DECISION_REQUIRED"],
            freshness=FreshnessState.FRESH
        )
    ]

    # Data Source 3: Telemetry & Dashboards
    dashboard_metrics = [
        DashboardMetric(
            id="METRIC-AUTH-01",
            name="OAuth2 Token Generation Rate",
            category="Throughput",
            current_value=14250.0,
            unit="RPS",
            status="NORMAL",
            baseline_value=15000.0,
            threshold_critical=8000.0,
            trend="STABLE",
            history=[
                MetricSeriesPoint(time="07:00", value=15100),
                MetricSeriesPoint(time="07:15", value=14800),
                MetricSeriesPoint(time="07:30", value=14200),
                MetricSeriesPoint(time="07:45", value=14100),
                MetricSeriesPoint(time="08:00", value=14300),
                MetricSeriesPoint(time="08:30", value=14250),
                MetricSeriesPoint(time="09:00", value=14250)
            ],
            freshness=FreshnessState.FRESH
        ),
        DashboardMetric(
            id="METRIC-AUTH-02",
            name="JWT Signature Validation Error Rate",
            category="Error Rate",
            current_value=18.6,
            unit="%",
            status="CRITICAL",
            baseline_value=0.02,
            threshold_critical=5.0,
            trend="RISING",
            history=[
                MetricSeriesPoint(time="07:00", value=0.02),
                MetricSeriesPoint(time="07:15", value=12.4),
                MetricSeriesPoint(time="07:30", value=19.1),
                MetricSeriesPoint(time="07:45", value=17.8),
                MetricSeriesPoint(time="08:00", value=18.2),
                MetricSeriesPoint(time="08:30", value=18.4),
                MetricSeriesPoint(time="09:00", value=18.6)
            ],
            freshness=FreshnessState.FRESH
        ),
        DashboardMetric(
            id="METRIC-AUTH-03",
            name="API Gateway JWKS Cache Stale Node Ratio",
            category="Edge Cache",
            current_value=42.5,
            unit="%",
            status="CRITICAL",
            baseline_value=0.0,
            threshold_critical=1.0,
            trend="HIGH_STABLE",
            history=[
                MetricSeriesPoint(time="07:00", value=0.0),
                MetricSeriesPoint(time="07:15", value=42.5),
                MetricSeriesPoint(time="07:30", value=42.5),
                MetricSeriesPoint(time="07:45", value=42.5),
                MetricSeriesPoint(time="08:00", value=42.5),
                MetricSeriesPoint(time="08:30", value=42.5),
                MetricSeriesPoint(time="09:00", value=42.5)
            ],
            freshness=FreshnessState.FRESH
        ),
        DashboardMetric(
            id="METRIC-AUTH-04",
            name="Redis Token Store Latency p99",
            category="Database",
            current_value=14.2,
            unit="ms",
            status="NORMAL",
            baseline_value=12.0,
            threshold_critical=100.0,
            trend="FALLING",
            history=[
                MetricSeriesPoint(time="07:00", value=11.5),
                MetricSeriesPoint(time="07:15", value=12.1),
                MetricSeriesPoint(time="07:30", value=18.5),
                MetricSeriesPoint(time="08:00", value=240.0),
                MetricSeriesPoint(time="08:30", value=22.0),
                MetricSeriesPoint(time="09:00", value=14.2)
            ],
            freshness=FreshnessState.FRESH
        )
    ]

    # Data Source 4: Ownership Changes
    ownership_changes = [
        OwnershipChange(
            id="OWN-4091",
            timestamp="2026-09-03T09:30:00Z",
            previous_lead="Marcus Vance (Shift Alpha)",
            new_lead="Elena Rostova (Shift Beta)",
            outgoing_shift="Alpha Shift (01:00-09:30 UTC)",
            incoming_shift="Beta Shift (09:30-18:00 UTC)",
            team="Identity & Access SRE Team",
            handover_type="ROUTINE",
            notes="Formal shift rotation handover during ongoing SEV-1 incident. Structured Handover Workspace active.",
            freshness=FreshnessState.FRESH
        )
    ]

    # Data Source 5: Action Logs with State Snapshots
    action_logs = [
        ActionLog(
            id="ACT-1001",
            timestamp="2026-09-03T07:00:00Z",
            actor="Vault Scheduler (Automation)",
            action_name="Vault Key Rotation execution to v4.1",
            description="Automated rotation of OAuth signing key `id-jwt-sig-key` in HashiCorp Vault.",
            target_component="Vault KMS / Identity Core",
            impact_level=ImpactLevel.MEDIUM,
            status=ActionStatus.EXECUTED,
            is_reversible=True,
            requires_two_person_review=False,
            executed_at="2026-09-03T07:00:00Z",
            approved_by="Automated Schedule Policy #882",
            before_state={"signing_key_version": "v3.9", "key_status": "ACTIVE"},
            after_state={"signing_key_version": "v4.1", "key_status": "ACTIVE"},
            rollback_state={"signing_key_version": "v3.9", "key_status": "ACTIVE"},
            details={"new_key_version": "v4.1", "prev_key_version": "v3.9"},
            freshness=FreshnessState.FRESH
        ),
        ActionLog(
            id="ACT-1002",
            timestamp="2026-09-03T07:50:00Z",
            actor="Marcus Vance",
            action_name="Flush Redis Session Connection Pool",
            description="Attempted flush of active Redis session locks to resolve auth error storm.",
            target_component="Redis Cluster East-1",
            impact_level=ImpactLevel.HIGH,
            status=ActionStatus.ROLLED_BACK,
            is_reversible=True,
            requires_two_person_review=True,
            executed_at="2026-09-03T07:52:00Z",
            approved_by="Marcus Vance (Emergency Override)",
            approver_1="Marcus Vance",
            approver_2="Devon Zhao",
            rollback_action_id="ACT-1002-RB",
            rollback_executed_at="2026-09-03T08:10:00Z",
            rollback_by="Marcus Vance",
            rollback_reason="Latency spiked to 240ms due to connection lock contention",
            before_state={"redis_p99_latency_ms": 18.5, "error_rate_percent": 18.6},
            after_state={"redis_p99_latency_ms": 240.0, "error_rate_percent": 18.6},
            rollback_state={"redis_p99_latency_ms": 14.2, "error_rate_percent": 18.6},
            details={"latency_spike_observed_ms": 240, "reason": "Connection lock contention spike"},
            freshness=FreshnessState.FRESH
        ),
        ActionLog(
            id="ACT-1003",
            timestamp="2026-09-03T09:15:00Z",
            actor="Elena Rostova",
            action_name="Force API Gateway JWKS Public Key Cache Invalidation",
            description="Publish forced invalidation broadcast signal `PUB_JWKS_FLUSH` to all 120 API Edge Gateways.",
            target_component="API Edge Gateway Network",
            impact_level=ImpactLevel.HIGH,
            status=ActionStatus.PENDING_REVIEW,
            is_reversible=True,
            requires_two_person_review=True,
            before_state={"jwt_error_rate_percent": 18.6, "stale_cache_ratio_percent": 42.5},
            after_state={"jwt_error_rate_percent": 0.02, "stale_cache_ratio_percent": 0.0},
            rollback_state={"jwt_error_rate_percent": 18.6, "stale_cache_ratio_percent": 42.5},
            details={"target_gateways_count": 120, "expected_resolution": "Clears 401 JWT validation error spike"},
            freshness=FreshnessState.FRESH
        ),
        ActionLog(
            id="ACT-1004",
            timestamp="2026-09-03T09:20:00Z",
            actor="Elena Rostova",
            action_name="Rollback Vault Token Signing Key from v4.1 -> v3.9",
            description="Emergency rollback of signing key version in Vault KMS if edge cache invalidation fails.",
            target_component="Vault KMS",
            impact_level=ImpactLevel.CRITICAL,
            status=ActionStatus.PENDING_REVIEW,
            is_reversible=True,
            requires_two_person_review=True,
            before_state={"signing_key_version": "v4.1"},
            after_state={"signing_key_version": "v3.9"},
            rollback_state={"signing_key_version": "v4.1"},
            details={"fallback_action": True, "target_key_version": "v3.9"},
            freshness=FreshnessState.FRESH
        )
    ]

    return {
        "incident_notes": incident_notes,
        "chat_excerpts": chat_excerpts,
        "dashboard_metrics": dashboard_metrics,
        "ownership_changes": ownership_changes,
        "action_logs": action_logs
    }


def get_initial_hypotheses_and_evidence() -> Dict[str, Any]:
    """Generates hypotheses and evidence graph for the shift handover workspace."""
    evidence_list = [
        Evidence(
            id="EVID-01",
            hypothesis_id="HYPO-01",
            source_type=SourceType.CHAT,
            source_id="CHAT-8812",
            title="API Gateway JWKS Cache Timeout",
            snippet="Priya Patel confirmed Edge Gateways hold 4-hour JWKS cache and missed invalidation webhook trigger.",
            impact=EvidenceImpact.SUPPORTS,
            added_by="Marcus Vance",
            added_at="2026-09-03T07:45:00Z"
        ),
        Evidence(
            id="EVID-02",
            hypothesis_id="HYPO-01",
            source_type=SourceType.METRIC,
            source_id="METRIC-AUTH-03",
            title="42.5% Edge Cache Stale Node Ratio",
            snippet="Metric METRIC-AUTH-03 shows exactly 42.5% of edge nodes are using stale public keys post-rotation.",
            impact=EvidenceImpact.SUPPORTS,
            added_by="Marcus Vance",
            added_at="2026-09-03T07:48:00Z"
        ),
        Evidence(
            id="EVID-03",
            hypothesis_id="HYPO-02",
            source_type=SourceType.ACTION_LOG,
            source_id="ACT-1002",
            title="Redis Flush Caused Latency Spike without Resolving Errors",
            snippet="Flushing Redis connection pool increased latency to 240ms while 401 error rate remained 18.6%. Action rolled back.",
            impact=EvidenceImpact.REFUTES,
            added_by="Elena Rostova",
            added_at="2026-09-03T08:20:00Z"
        ),
        Evidence(
            id="EVID-04",
            hypothesis_id="HYPO-03",
            source_type=SourceType.METRIC,
            source_id="METRIC-AUTH-01",
            title="Token Generation RPS Remains Healthy",
            snippet="Identity Core Pod throughput is 14,250 RPS (normal range), refuting Core Pod crash or CPU throttling.",
            impact=EvidenceImpact.REFUTES,
            added_by="Marcus Vance",
            added_at="2026-09-03T08:30:00Z"
        )
    ]

    hypotheses = [
        Hypothesis(
            id="HYPO-01",
            title="Edge Gateway JWKS Public Key Cache Mismatch post Vault Rotation",
            description=(
                "Vault key rotation at 07:00 UTC generated v4.1 JWT tokens, but 42.5% of API Edge Gateways missed the cache invalidation "
                "webhook due to listener timeout. Edge nodes are attempting to validate v4.1 signatures using cached v3.9 public keys."
            ),
            status=HypothesisStatus.CONFIRMED,
            confidence_score=0.92,
            created_by="Priya Patel / Marcus Vance",
            created_at="2026-09-03T07:45:00Z",
            updated_at="2026-09-03T08:50:00Z",
            evidence_ids=["EVID-01", "EVID-02"]
        ),
        Hypothesis(
            id="HYPO-02",
            title="Redis Token Store Session Pool Corruption",
            description="Hypothesis that Redis session store connection lock contention was causing token validation failures.",
            status=HypothesisStatus.DISPROVED,
            confidence_score=0.08,
            created_by="Marcus Vance",
            created_at="2026-09-03T07:30:00Z",
            updated_at="2026-09-03T08:20:00Z",
            evidence_ids=["EVID-03"]
        ),
        Hypothesis(
            id="HYPO-03",
            title="Identity Core Pod CPU Throttling or Pod Crash Loop",
            description="Hypothesis that core auth service container pods were overwhelmed by auth request volume.",
            status=HypothesisStatus.DISPROVED,
            confidence_score=0.03,
            created_by="Devon Zhao",
            created_at="2026-09-03T07:15:00Z",
            updated_at="2026-09-03T08:30:00Z",
            evidence_ids=["EVID-04"]
        )
    ]

    return {
        "hypotheses": hypotheses,
        "evidence_list": evidence_list
    }


def create_initial_workspace() -> ShiftHandoverWorkspace:
    """Assembles initial complete Shift Handover Workspace with SHA-256 hash-chained audit entries."""
    data_sources = get_initial_data_sources()
    hypo_evid = get_initial_hypotheses_and_evidence()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    freshness = DataFreshnessStatus(
        incident_notes=FreshnessState.FRESH,
        chat_excerpts=FreshnessState.FRESH,
        dashboards=FreshnessState.FRESH,
        ownership_changes=FreshnessState.FRESH,
        action_logs=FreshnessState.FRESH,
        last_checked=now
    )

    source_resilience = [
        SourceResilienceItem(
            source_name="Incident Notes",
            state=FreshnessState.FRESH,
            last_updated="2026-09-03T08:45:00Z",
            usability="FULL",
            impact_assessment="Operational context & severity metadata intact.",
            evidence_count=2
        ),
        SourceResilienceItem(
            source_name="Slack Chat Feed",
            state=FreshnessState.FRESH,
            last_updated="2026-09-03T09:10:05Z",
            usability="FULL",
            impact_assessment="Engineering discussions and key takeaways available.",
            evidence_count=5
        ),
        SourceResilienceItem(
            source_name="Telemetry Dashboards",
            state=FreshnessState.FRESH,
            last_updated="2026-09-03T09:00:00Z",
            usability="FULL",
            impact_assessment="Error rates and p99 latency graphs updating normally.",
            evidence_count=4
        ),
        SourceResilienceItem(
            source_name="Ownership Rotation",
            state=FreshnessState.FRESH,
            last_updated="2026-09-03T09:30:00Z",
            usability="FULL",
            impact_assessment="Shift leads and team handover records verified.",
            evidence_count=1
        ),
        SourceResilienceItem(
            source_name="Action Logs",
            state=FreshnessState.FRESH,
            last_updated="2026-09-03T09:20:00Z",
            usability="FULL",
            impact_assessment="Execution status and reversibility state intact.",
            evidence_count=4
        )
    ]

    # Build SHA-256 Hash-Chained Audit Trail
    audit_trail_raw = [
        {
            "id": "AUD-5001",
            "timestamp": "2026-09-03T07:10:00Z",
            "actor": "Marcus Vance",
            "role": "SRE / On-Call Specialist",
            "action_type": "INCIDENT_DECLARED",
            "description": "Declared SEV-1 incident for Enterprise Identity Service",
            "metadata": {"severity": "SEV-1", "incident_id": "INC-9042"}
        },
        {
            "id": "AUD-5002",
            "timestamp": "2026-09-03T08:10:00Z",
            "actor": "Marcus Vance",
            "role": "SRE / On-Call Specialist",
            "action_type": "ACTION_ROLLED_BACK",
            "description": "Rolled back Redis flush operation ACT-1002 due to latency spike",
            "metadata": {"action_id": "ACT-1002"}
        },
        {
            "id": "AUD-5003",
            "timestamp": "2026-09-03T09:30:00Z",
            "actor": "System Handover Engine",
            "role": "Incident Commander / Handover Lead",
            "action_type": "HANDOVER_INITIALIZED",
            "description": "Shift Handover workspace initialized for Alpha -> Beta shift transition",
            "metadata": {"outgoing": "Marcus Vance", "incoming": "Elena Rostova"}
        }
    ]

    audit_trail: List[AuditEntry] = []
    prev_hash = GENESIS_HASH
    for item in audit_trail_raw:
        h = compute_audit_hash(item["id"], item["timestamp"], item["actor"], item["role"], item["action_type"], item["description"], item["metadata"], prev_hash)
        entry = AuditEntry(
            id=item["id"],
            timestamp=item["timestamp"],
            actor=item["actor"],
            role=item["role"],
            action_type=item["action_type"],
            description=item["description"],
            metadata=item["metadata"],
            previous_hash=prev_hash,
            record_hash=h
        )
        audit_trail.append(entry)
        prev_hash = h

    change_reviews = [
        ChangeReviewRequest(
            action_id="ACT-1003",
            action_name="Force API Gateway JWKS Public Key Cache Invalidation",
            requested_by="Elena Rostova",
            target_component="API Edge Gateway Network",
            impact_level=ImpactLevel.HIGH,
            justification="Flushes stale v3.9 public key cache across 120 edge nodes to resolve 18.6% JWT signature validation errors.",
            proposed_at="2026-09-03T09:15:00Z",
            status="PENDING_APPROVAL"
        )
    ]

    unresolved_actions = [
        act for act in data_sources["action_logs"] if act.status in [ActionStatus.PENDING_REVIEW, ActionStatus.APPROVED]
    ]

    workspace = ShiftHandoverWorkspace(
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
        ),
        hypotheses=hypo_evid["hypotheses"],
        evidence_list=hypo_evid["evidence_list"],
        unresolved_actions=unresolved_actions,
        freshness=freshness,
        source_resilience=source_resilience,
        audit_trail=audit_trail,
        change_reviews=change_reviews
    )

    return workspace
