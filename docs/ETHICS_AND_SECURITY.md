# Ethics, Privacy & Data Security Policy

## 1. Data Privacy & PII Scrubbing
- **Operational Chat Transcripts**: Operational messages ingested from Slack or Microsoft Teams pass through a PII Redaction Filter before persistence. User passwords, secret keys, bearer tokens, and personally identifiable employee data are automatically replaced with standard tokens (e.g. `[REDACTED_BEARER_TOKEN]`).
- **Data Retention**: Shift handover evidence graphs and audit logs are retained for 90 days in compliance with enterprise audit policies.

---

## 2. Security & Role-Based Access Control (RBAC)
- **Role Scoping**:
  - `SRE / On-Call Specialist`: Full access to execution triggers, raw metric traces, evidence linking, and 1-click rollback paths.
  - `Incident Commander`: Access to executive shift summaries, risk score gauges, change review sign-offs, and final handover acceptance.
  - `Enterprise App Developer / Stakeholder`: Read-only access to blast radius indicators, application SLA status, and resolution ETA.
- **Two-Person Change Review Rule**: High-impact operational changes (Vault KMS key version changes, rate-limit overrides, global cache invalidations) require explicit digital authorization signatures from both the Outgoing Shift Lead and Incoming Shift Lead.

---

## 3. Immutable Audit Trail & Non-Repudiation
- Every action—including hypothesis creation, evidence linking, data source status toggling, change approvals, and execution rollbacks—is appended to an immutable JSON audit log.
- Audit entries record UTC timestamp, actor identity, active role, action type, description, and cryptographic hash verification.
