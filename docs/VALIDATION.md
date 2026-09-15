# Stakeholder Validation Framework & Operational Runbook

## 1. User Research Honesty Policy

To maintain evaluation integrity, the **Enterprise Identity Service Shift-Handover Workspace** strictly distinguishes between seeded sample tasks and genuine user research observations.

> [!CAUTION]
> Pre-populated test results distort evaluation integrity. In this repository, all stakeholder validation tasks default to **`NOT_TESTED`**. Summary statistics are computed **exclusively** from recorded **`OBSERVED_VALIDATION`** entries.
> 
> Current Status: **`NOT_TESTED` (Real observation pending)**

---

## 2. Validation Status Classifications

| Status Label | Description | Calculation Inclusion |
| :--- | :--- | :--- |
| **`NOT_TESTED`** | Task initialized in workspace, awaiting real user observation. | Excluded from completion rate |
| **`DEMO_SAMPLE`** | Sample dataset for UI demonstration purposes. | Excluded from completion rate |
| **`OBSERVED_VALIDATION`** | Recorded user observation submitted via API (`POST /api/stakeholder-validation`). | **Included** in completion rate |

---

## 3. Role-Specific Evaluation Protocol (Validation Runbook)

### Session A: SRE / On-Call Specialist Session
**Target Role**: SRE / On-Call Specialist  
**Headers Required**: `X-User-Role: SRE / On-Call Specialist`, `X-User-Name: <Participant Name>`  
**Operational Tasks**:
1. Open active SEV-1 incident workspace (`INC-9042`).
2. Inspect the 5 enterprise source freshness statuses (`fresh-notes`, `fresh-chat`, `fresh-metrics`, `fresh-ownership`, `fresh-actions`).
3. Identify degraded or missing source indicators (e.g., Slack Chat stream MISSING state).
4. Inspect active hypotheses in the evidence graph (`HYPO-01`).
5. Inspect supporting evidence snippets (`EVID-01`, `EVID-02`).
6. Create or update an operational hypothesis via the workspace UI.
7. Review unresolved high-impact action queue (`ACT-1003`).
8. Execute an approved action after dual approval is granted.
9. Verify SHA-256 audit record appended for executed action.
10. Perform 1-click state snapshot rollback and verify physical metric restoration.

### Session B: Incident Commander / Handover Lead Session
**Target Role**: Incident Commander / Handover Lead  
**Headers Required**: `X-User-Role: Incident Commander / Handover Lead`, `X-User-Name: <Participant Name>`  
**Operational Tasks**:
1. Review overall incident summary and context loss risk score.
2. Review evidence-backed hypotheses and confidence scores.
3. Review source resilience matrix usability guidance.
4. Review pending change review requests (`ACT-1003`).
5. Provide Approval 2 for change review request.
6. Complete formal shift handover sign-off wizard (`outgoing_user` vs `incoming_user`).

### Session C: Enterprise App Developer / Stakeholder Session
**Target Role**: Enterprise App Developer / Stakeholder  
**Headers Required**: `X-User-Role: Enterprise App Developer / Stakeholder`, `X-User-Name: <Participant Name>`  
**Operational Tasks**:
1. View incident context and impact summary across 480+ downstream applications.
2. View permitted evidence snippets.
3. Inspect data source freshness indicators.
4. Verify restricted mutation controls (execution, rollback, approval) return `HTTP 403 Forbidden` or are hidden.
5. Confirm handover lead contact details and shift transition state.

---

## 4. Recording Real Observations

Participant observations must be recorded using the API endpoint or UI form:

```bash
curl -X POST http://localhost:8000/api/stakeholder-validation \
  -H "Content-Type: application/json" \
  -H "X-User-Role: SRE / On-Call Specialist" \
  -H "X-User-Name: Elena Rostova" \
  -d '{
    "task_id": "TASK-01",
    "completed": true,
    "completion_time_sec": 14.5,
    "error_count": 0,
    "comments": "Participant located incoming shift lead in summary card in 14.5s.",
    "validation_status": "OBSERVED_VALIDATION"
  }'
```

---

## 5. Session Observation Sheet

For every live evaluation session, record:
- **Participant Role**: `SRE` / `Incident Commander` / `Developer`
- **Participant Identifier**: `<Name / Pseudonym>`
- **Task ID**: `TASK-01` through `TASK-08`
- **Start Time & End Time**: ISO UTC timestamp
- **Duration**: Elapsed time in seconds
- **Success/Failure**: `True` / `False`
- **Error Count**: Number of misplaced clicks or unfulfilled sub-steps
- **Qualitative Feedback**: Participant observations or notes
