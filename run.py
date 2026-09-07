"""
Launcher script for Enterprise Identity Service Shift-Handover Workspace.
"""

import sys
import uvicorn
import subprocess

def main():
    print("==================================================================")
    print(" Enterprise Identity Service - Resilient Shift Handover Workspace")
    print("==================================================================")
    print("Running automated test suite...")
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/test_backend.py", "-v"])
    if res.returncode != 0:
        print("❌ Test suite failed!")
        sys.exit(1)

    print("\n✅ All tests passed cleanly! Starting FastAPI Web Application on http://localhost:8000 ...")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
