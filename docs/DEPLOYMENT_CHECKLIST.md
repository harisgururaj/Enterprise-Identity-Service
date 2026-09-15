# Operational Deployment Checklist

## Pre-Deployment Verification
- [x] Python 3.10+ runtime verified.
- [x] Complete dependencies listed in `requirements.txt` (FastAPI, SQLAlchemy, Pydantic, Pytest, Uvicorn, Httpx, Playwright).
- [x] SQLite database schema initialized (`identity_workspace.db`).
- [x] Database health and readiness endpoints operational (`GET /health`, `GET /health/ready`).
- [x] Automated test suite execution: `python -m pytest tests/ -v` (21 PASSED / 3 XFAIL across 24 collected items).

## Deployment Procedure
1. **Navigate to Project Directory**:
   ```powershell
   cd C:\Users\haris\.gemini\antigravity\scratch\identity_shift_handover_workspace
   ```
2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **Execute Test Suite**:
   ```powershell
   python -m pytest tests/ -v
   ```
4. **Launch Application**:
   ```powershell
   python run.py
   ```
5. **Verify Live Application**:
   - Web App UI: `http://localhost:8000`
   - Readiness Check: `GET http://localhost:8000/health/ready` returns `{"status": "READY", "database": "CONNECTED"}`.
   - API Verification: `GET http://localhost:8000/api/audit/verify` returns `valid: true`.
