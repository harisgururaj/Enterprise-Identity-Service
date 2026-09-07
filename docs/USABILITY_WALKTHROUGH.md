# Usability & Operational Walkthrough Guide

This document provides a step-by-step walkthrough for evaluating the **Enterprise Identity Service Shift-Handover Workspace**.

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
3. Note the calculated **Handover Risk Score** (`12.5 / 100 - LOW`).

### Step 3: Investigate Hypothesis → Evidence Graph
1. Locate Hypothesis **HYP-101**: *"OAuth2 Token Signing Key Rotation Desynchronization"*.
2. Click **View Supporting Evidence** to open the modal drill-down.
3. Verify supporting evidence from `dashboard_metrics` (METRIC-AUTH-02 18.6% error rate) and `chat_excerpts` (Key rotation script run at 14:02 UTC).
4. Review confidence calculation (**92% HIGH Confidence**).

### Step 4: High-Impact Action & Two-Person Approval
1. Scroll to **Unresolved Operational Action Queue**.
2. Locate Action **ACT-1003**: *"Roll back OAuth2 Signing Key Set to Previous Key Version (v4.1.0)"*.
3. Click **Execute Action** as `Elena Rostova` (SRE). Observe error banner: `HTTP 403 Forbidden: High-impact action requires 2-person approval`.
4. Switch role header or click **Approve Action** as `Marcus Vance` (Incident Commander). Status updates to `PENDING_APPROVAL_2`.
5. Attempt to approve again as `Marcus Vance`. Observe error modal: `Dual Approval Failure: Same user cannot provide both approvals`.
6. Click **Approve Action** as `Elena Rostova` (SRE). Status updates to `APPROVED`.
7. Click **Execute Action**. Status updates to `EXECUTED`. Notice telemetry metric `METRIC-AUTH-02` updates from `18.6%` to `0.8%`.

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
2. Scroll to **Controlled Resilience Experiment**. View degradation metrics across 4 availability conditions.

### Step 9: Stakeholder Validation & Handover Sign-Off
1. Scroll to **Stakeholder Validation Workflow**. Note tasks default to `NOT_TESTED`.
2. Click **Record Observation** on Task 1, enter test metrics (`14.5 sec`), and submit. Observe task status update to `OBSERVED_VALIDATION`.
3. Scroll to **Shift Handover Sign-Off**.
4. Enter Outgoing Owner (`Marcus Vance`) and Incoming Owner (`Elena Rostova`).
5. Click **Complete Handover Sign-Off**. Confirm status updates to `SIGNED / ACCEPTED`.
