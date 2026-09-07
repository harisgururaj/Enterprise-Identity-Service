# Stakeholder Validation Framework & Record Protocol

## 1. User Research Honesty Policy

To maintain evaluation integrity, the **Enterprise Identity Service Shift-Handover Workspace** distinguishes between seeded sample tasks and genuine user research observations.

> [!CAUTION]
> Pre-populated test results can distort evaluation integrity. In this repository, all stakeholder validation tasks default to **`NOT_TESTED`**. Summary statistics are computed **exclusively** from recorded **`OBSERVED_VALIDATION`** entries.

---

## 2. Validation Status Classifications

| Status Label | Description | Calculation Inclusion |
| :--- | :--- | :--- |
| **`NOT_TESTED`** | Task initialized in workspace, awaiting user observation. | Excluded from completion rate |
| **`DEMO_SAMPLE`** | Sample dataset for UI demonstration purposes. | Excluded from completion rate |
| **`OBSERVED_VALIDATION`** | Recorded user observation submitted via API (`POST /api/stakeholder-validation`). | **Included** in completion rate |

---

## 3. Evaluation Tasks Protocol

The validation workflow exposes 8 standard operational tasks for on-call engineers, incident commanders, and stakeholders:

1. **TASK-01**: Find current incident owner and incoming shift owner.
2. **TASK-02**: Identify highest-confidence hypothesis in evidence graph.
3. **TASK-03**: Determine whether telemetry source stream is fresh or degraded.
4. **TASK-04**: Locate unresolved high-impact operational actions.
5. **TASK-05**: Determine dual approval history and approver identities.
6. **TASK-06**: Execute action rollback demonstration if authorized.
7. **TASK-07**: Verify audit trail hash chain integrity and tamper detection.
8. **TASK-08**: Complete shift handover sign-off workflow.

---

## 4. Recording Real Observations

Real observations are recorded via frontend or API call:

```bash
curl -X POST http://localhost:8000/api/stakeholder-validation \
  -H "Content-Type: application/json" \
  -H "X-User-Role: Enterprise App Developer / Stakeholder" \
  -H "X-User-Name: Devon Zhao" \
  -d '{
    "task_id": "TASK-01",
    "completed": true,
    "completion_time_sec": 14.2,
    "error_count": 0,
    "comments": "User easily found incoming owner Elena Rostova in summary card.",
    "validation_status": "OBSERVED_VALIDATION"
  }'
```
