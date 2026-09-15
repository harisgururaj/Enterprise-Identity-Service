# Usability & Operational Walkthrough Guide

This document provides a step-by-step walkthrough for evaluating the **Enterprise Identity Service Shift-Handover Workspace**.

---

## 📸 Evaluator Screenshot Checklist

The following 12 operational screenshots demonstrate complete visual usability of the workspace.

> [!NOTE]
> Labeling Protocol: Screenshots captured in your environment must be saved in `docs/screenshots/` and linked below.

| # | Screenshot Item | Target View / Component | Status |
| :--- | :--- | :--- | :---: |
| **1** | **Authenticated SRE View** | Header bar showing `X-User-Role: SRE / On-Call Specialist` and `X-User-Name: Elena Rostova`. | `[SCREENSHOT TO CAPTURE]` |
| **2** | **SRE Workspace Dashboard** | Main operational view showing SEV-1 incident summary and risk score (`12.4 / 100`). | `[SCREENSHOT TO CAPTURE]` |
| **3** | **Source Freshness Panel** | 5-source freshness indicators (`fresh-notes`, `fresh-chat`, `fresh-metrics`, `fresh-ownership`, `fresh-actions`). | `[SCREENSHOT TO CAPTURE]` |
| **4** | **Missing / Degraded Source State** | Workspace UI displaying `MISSING` chat stream fallback notice and updated risk score. | `[SCREENSHOT TO CAPTURE]` |
| **5** | **Hypothesis + Evidence Graph** | Drill-down modal showing `HYPO-01` linked supporting evidence (`EVID-01`, `EVID-02`). | `[SCREENSHOT TO CAPTURE]` |
| **6** | **Change Review Request** | Unresolved action queue showing high-impact change request `ACT-1003`. | `[SCREENSHOT TO CAPTURE]` |
| **7** | **Two-Person Dual Approval** | Approval state machine displaying distinct `approver_1` (`Marcus Vance`) and `approver_2` (`Elena Rostova`). | `[SCREENSHOT TO CAPTURE]` |
| **8** | **Action Execution & Rollback** | 1-Click Rollback restoring telemetry error rate from `0.02%` back to `18.6%` using `before_state` snapshot. | `[SCREENSHOT TO CAPTURE]` |
| **9** | **Cryptographic Audit History** | SHA-256 hash-chained audit log table and `/api/audit/verify` verification badge. | `[SCREENSHOT TO CAPTURE]` |
| **10** | **Incident Commander View** | Shift transition overview and dual-approval management for Incident Commander role. | `[SCREENSHOT TO CAPTURE]` |
| **11** | **Stakeholder Restricted View** | Developer/Stakeholder read-only view with restricted action execution buttons hidden/disabled. | `[SCREENSHOT TO CAPTURE]` |
| **12** | **Handover Sign-Off Wizard** | Shift handover sign-off modal requiring distinct `outgoing_user` and `incoming_user` identities. | `[SCREENSHOT TO CAPTURE]` |

---

## Operational Walkthrough Flow

### Step 1: Open the Application & Authenticate
1. Launch backend (`python run.py`) and navigate to `http://localhost:8000`.
2. Select **SRE / On-Call Specialist** in the top navigation role dropdown.
3. Observe active headers (`X-User-Name: Elena Rostova`, `X-User-Role: SRE / On-Call Specialist`).

### Step 2: Inspect 5 Enterprise Data Sources & Source Health
1. View the **Source Resilience Health Matrix** card.
2. Confirm statuses for all 5 enterprise streams:
   - Incident Notes (`FRESH`)
   - Chat Excerpts (`FRESH`)
   - Dashboard Metrics (`FRESH`)
   - Ownership Log (`FRESH`)
   - Action Log (`FRESH`)
3. Note the calculated **Handover Risk Score** (`12.4 / 100 - LOW`).

### Step 3: Investigate Hypothesis → Evidence Graph
1. Locate Hypothesis **HYPO-01**: *"OAuth2 Token Signing Key Rotation Desynchronization"*.
2. Click **View Supporting Evidence** to open the modal drill-down.
3. Verify supporting evidence from `dashboard_metrics` (METRIC-AUTH-02 18.6% error rate) and `chat_excerpts` (Key rotation script run at 07:00 UTC).
4. Review confidence calculation (**92% CONFIRMED Confidence**).

### Step 4: High-Impact Action & Two-Person Approval
1. Scroll to **Unresolved Operational Action Queue**.
2. Locate Action **ACT-1003**: *"Force API Gateway JWKS Public Key Cache Invalidation"*.
3. Click **Execute Action** as `Elena Rostova` (SRE). Observe error banner: `HTTP 403 Forbidden: High-impact action requires 2-person approval`.
4. Switch role header or click **Approve Action** as `Marcus Vance` (Incident Commander). Status updates to `PENDING_APPROVAL_2`.
5. Attempt to approve again as `Marcus Vance`. Observe error modal: `Dual Approval Failure: Same user cannot provide both approvals`.
6. Click **Approve Action** as `Elena Rostova` (SRE). Status updates to `APPROVED`.
7. Click **Execute Action**. Status updates to `EXECUTED`. Notice telemetry metric `METRIC-AUTH-02` updates from `18.6%` to `0.02%`.

### Step 5: Execute Generic State Snapshot Rollback
1. Click **Rollback Action** on **ACT-1003**.
2. Provide rationale: *"Emergency state restoration test"*.
3. Observe status update to `ROLLED_BACK`.
4. Verify telemetry metric `METRIC-AUTH-02` is physically restored back to `18.6%` using the captured `before_state` snapshot.
5. Attempt to click **Rollback Action** a second time. Observe error modal: `HTTP 400 Bad Request: Action has already been rolled back`.

### Step 6: Verify SHA-256 Audit Trail & Tamper Detection
1. Scroll to the **Cryptographic Audit Trail** table.
2. Click **Verify Chain Integrity**. Confirm green badge: `Audit Chain Verification PASSED (Valid: True)`.
3. Click **Simulate Tamper Test**. Record `AUD-5001` is modified in-memory.
4. Click **Verify Chain Integrity** again. Confirm red error badge: `Audit Chain Tampering Detected! First Invalid Record: AUD-5001`.

### Step 7: Test Source Degradation Resilience
1. In the **Source Resilience Panel**, toggle `chat_excerpts` status to `MISSING`.
2. Notice chat evidence turns grayed out with `UNAVAILABLE` status.
3. Confirm workspace remains fully operational using the remaining 4 data sources, with Handover Risk Score automatically re-adjusting.

### Step 8: View Controlled Benchmark & Resilience Experiments
1. Scroll to **Controlled Benchmark Evaluation**. View reproducible Monte Carlo results (Baseline `42.2 min` vs Solution `14.4 min`, `65.9%` reduction).
2. Scroll to **Controlled Resilience Experiment**. View degradation metrics across 8 availability conditions.

### Step 9: Stakeholder Validation & Handover Sign-Off
1. Scroll to **Stakeholder Validation Workflow**. Note tasks default to `NOT_TESTED`.
2. Click **Record Observation** on Task 1, enter test metrics (`14.5 sec`), and submit. Observe task status update to `OBSERVED_VALIDATION`.
3. Scroll to **Shift Handover Sign-Off**.
4. Enter Outgoing Owner (`Marcus Vance`) and Incoming Owner (`Elena Rostova`).
5. Click **Complete Handover Sign-Off**. Confirm status updates to `ACCEPTED`.
