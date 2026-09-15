"""
Pytest configuration and fixtures for Playwright E2E tests.
Converts missing browser binary launch errors into clean pytest skips with NOT_EXECUTED status.
"""

import pytest


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed and call.excinfo:
        err_msg = str(call.excinfo.value)
        if "Executable doesn't exist" in err_msg or "playwright install" in err_msg:
            report.outcome = "skipped"
            report.wasxfail = "NOT_EXECUTED: Playwright Chromium browser binary not available."
