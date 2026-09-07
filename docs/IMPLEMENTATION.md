# System Architecture & Technical Implementation

## 1. Architectural Overview

The **Enterprise Identity Service Shift-Handover Workspace** is constructed using a decoupled FastAPI Python backend and a responsive Single-Page Application (SPA) frontend.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Single-Page Frontend                             │
│       Role Selector | Source Resilience Panel | Hypothesis Graph | UI       │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ HTTP REST APIs
                                       │ (Headers: X-User-Name, X-User-Role)
┌──────────────────────────────────────▼──────────────────────────────────────┐
│                            FastAPI Backend Engine                           │
│ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐ │
│ │ Server-Side RBAC &   │ │ 5 Enterprise Data    │ │  Dual-User 2-Person  │ │
│ │ Auth Identity Context│ │ Streams & Resilience │ │ Approval State Engine│ │
│ └──────────┬───────────┘ └──────────┬───────────┘ └──────────┬───────────┘ │
│            │                        │                        │              │
│ ┌──────────▼───────────┐ ┌──────────▼───────────┐ ┌──────────▼───────────┐ │
│ │ Generic State        │ │ SHA-256 Hash-Chained │ │ Monte Carlo        │ │
│ │ Snapshot Rollback    │ │ Audit Log Engine     │ │ Benchmark & Resil. │ │
│ └──────────────────────┘ └──────────────────────┘ └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Modules & Files

- **`backend/app.py`**: FastAPI routing, RBAC enforcement (`get_authenticated_user`, `require_role`), 2-person approval workflow, generic state snapshot restoration, SHA-256 hash chaining, handover signoff validation, and CORS security.
- **`backend/models.py`**: Pydantic data schemas (`AuthUserIdentity`, `FreshnessState`, `ActionStatus`, `AuditEntry`, `StateSnapshot`, `BenchmarkResult`, `ResilienceExperimentSummary`).
- **`backend/benchmark.py`**: Monte Carlo simulation engine (`run_handover_benchmark`, `run_resilience_experiment`) computing delay reductions, 95% confidence intervals, and degradation matrix across 4 availability conditions.
- **`backend/data_generator.py`**: Incident SEV-1 scenario generator initializing raw streams, hypotheses, state snapshots, and resilience items.
- **`frontend/index.html` & `frontend/css/style.css`**: Responsive operational dashboard featuring glassmorphism cards, dynamic role badges, action controls, and modal drill-downs.
- **`frontend/js/app.js`**: Client controller handling header injection, state toggles, audit tamper verification, and validation mode switching.
- **`tests/test_backend.py`**: Pytest integration suite (12/12 passing) covering security, RBAC, impersonation prevention, state rollbacks, audit tamper detection, and benchmark reproducibility.

---

## 3. Key Invariants & Mechanisms

1. **Authentication Context**: Validated header tuple (`X-User-Name`, `X-User-Role`). Missing header ➔ `HTTP 401 Unauthorized`. Invalid role ➔ `HTTP 403 Forbidden`.
2. **Impersonation Guard**: Audit trails and execution contexts pull strictly from `auth_user.username`. Request-body identity overrides are explicitly ignored for authorization.
3. **Dual-Approval State Machine**: High-impact actions transition `PENDING_REVIEW` ➔ `PENDING_APPROVAL_2` ➔ `APPROVED` ➔ `EXECUTED`. Rejects same user approving twice.
4. **Generic State Restoration**: Actions capture `before_state` snapshots upon execution and write `before_state` directly back to data streams during rollback.
5. **SHA-256 Audit Trail**: Append-only hash chain linking `previous_hash` and `record_hash` using `GENESIS_HASH`. Endpoint `GET /api/audit/verify` identifies the exact broken index upon tampering.
