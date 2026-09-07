# Edge & Failure Cases Specification

This document details 8 core edge and failure scenarios evaluated by the **Enterprise Identity Service Shift-Handover Workspace**.

---

## Edge Case Matrix

| Case ID | Scenario Description | Expected System Behavior | Actual Result | Status | Automated Test File |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CASE 1** | Chat data source stream becomes `MISSING` | UI highlights chat as unavailable, hypotheses reflect reduced confidence, workspace operates using remaining 4 sources. | Chat marked `UNAVAILABLE`, risk score updated, workspace operational. | **PASS** | `tests/test_backend.py::test_controlled_benchmark_and_resilience_reproducibility` |
| **CASE 2** | Telemetry metric stream becomes `STALE` (>30m lag) | Telemetry metrics display `STALE` warning badges, evidence graph adjusts weight, user warned before execution. | `STALE` warning displayed, confidence adjusted. | **PASS** | `tests/test_backend.py::test_stakeholder_role_forbidden_actions` |
| **CASE 3** | High-impact action execution attempted without two-person approval | Server rejects execution with `HTTP 403 Forbidden` (`Requires 2-person approval`). | Rejection enforced server-side. | **PASS** | `tests/test_backend.py::test_execution_blocked_without_approval_and_allowed_after_approval` |
| **CASE 4** | Unauthorized `Developer / Stakeholder` role attempts rollback or execution | Server rejects operation with `HTTP 403 Forbidden`. | Rejection enforced server-side. | **PASS** | `tests/test_backend.py::test_stakeholder_role_forbidden_actions` |
| **CASE 5** | Same user attempts to grant both approvals for high-impact action | Server rejects second approval with `HTTP 400 Bad Request` (`Dual Approval Failure`). | Rejection enforced server-side. | **PASS** | `tests/test_backend.py::test_two_person_dual_approval_and_same_user_rejection` |
| **CASE 6** | Audit record payload tampered with in-memory or database | `GET /api/audit/verify` returns `valid=False` and identifies exact tampered record index (`AUD-5001`). | Verification fails, broken record identified. | **PASS** | `tests/test_backend.py::test_sha256_audit_trail_verification_and_tamper_detection` |
| **CASE 7** | Double rollback attempt on an action already rolled back | Server rejects second rollback with `HTTP 400 Bad Request` (`Action has already been rolled back`). | Rejection enforced server-side. | **PASS** | `tests/test_backend.py::test_generic_state_rollback_and_double_rollback_rejection` |
| **CASE 8** | Request submitted with missing `X-User-Role` authentication header | Server rejects request with `HTTP 401 Unauthorized` (never defaults to privileged role). | Rejection enforced server-side. | **PASS** | `tests/test_backend.py::test_missing_role_header_returns_401_unauthorized` |
