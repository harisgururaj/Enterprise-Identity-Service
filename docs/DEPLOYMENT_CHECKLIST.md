# Operational Deployment Checklist

## Pre-Deployment Verification
- [x] Python 3.10+ runtime verified.
- [x] Complete dependencies listed in `requirements.txt`.
- [x] Automated test suite execution: `python -m pytest tests/test_backend.py -v` (8/8 PASSED).

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
   python -m pytest tests/test_backend.py -v
   ```
4. **Launch Application**:
   ```powershell
   python run.py
   ```
5. **Verify Live Application**:
   - Web App UI: `http://localhost:8000`
   - API Verification: `GET http://localhost:8000/api/audit/verify` returns `valid: true`.
