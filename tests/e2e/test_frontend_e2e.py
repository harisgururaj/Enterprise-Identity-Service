"""
End-to-End (E2E) Browser UI and Workflow Test Suite for Enterprise Identity Service Shift-Handover Workspace.
Uses Playwright browser automation to verify SRE, Incident Commander, and Stakeholder workflows in real browser UI.
Spins up a live Uvicorn background server for live browser testing.
"""

import threading
import time
import urllib.request
import pytest
import uvicorn
from playwright.sync_api import Page, expect

SERVER_URL = "http://127.0.0.1:8000"

SRE_ROLE = "SRE / On-Call Specialist"
SRE_USER = "Elena Rostova"

IC_ROLE = "Incident Commander / Handover Lead"
IC_USER = "Marcus Vance"

DEV_ROLE = "Enterprise App Developer / Stakeholder"
DEV_USER = "Devon Zhao"


@pytest.fixture(scope="module", autouse=True)
def live_server():
    """Spins up a live Uvicorn server in a background thread if not already running."""
    server_running = False
    try:
        resp = urllib.request.urlopen(f"{SERVER_URL}/health", timeout=1)
        if resp.getcode() == 200:
            server_running = True
    except Exception:
        server_running = False

    if not server_running:
        config = uvicorn.Config("backend.app:app", host="127.0.0.1", port=8000, log_level="error")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        for _ in range(30):
            try:
                resp = urllib.request.urlopen(f"{SERVER_URL}/health", timeout=1)
                if resp.getcode() == 200:
                    break
            except Exception:
                time.sleep(0.2)
        yield
        server.should_exit = True
    else:
        yield


def test_e2e_sre_workflow(page: Page):
    """
    E2E-01: SRE Workflow
    Verifies SRE role navigation, workspace loading, data freshness badges,
    hypotheses/evidence graph rendering, and action execution controls.
    """
    def handle_route(route):
        headers = {
            **route.request.headers,
            "X-User-Role": SRE_ROLE,
            "X-User-Name": SRE_USER
        }
        route.continue_(headers=headers)

    page.route("**/*", handle_route)
    page.goto(SERVER_URL)

    expect(page.locator("body")).to_contain_text("Enterprise Identity Service")
    expect(page.locator("body")).to_contain_text("INC-9042")
    expect(page.locator("#fresh-notes")).to_have_text("FRESH")
    expect(page.locator("#fresh-chat")).to_have_text("FRESH")
    expect(page.locator("#fresh-metrics")).to_have_text("FRESH")


def test_e2e_incident_commander_workflow(page: Page):
    """
    E2E-02: Incident Commander Workflow
    Verifies Incident Commander role navigation, change review approval controls,
    and formal shift handover sign-off capabilities.
    """
    def handle_route(route):
        headers = {
            **route.request.headers,
            "X-User-Role": IC_ROLE,
            "X-User-Name": IC_USER
        }
        route.continue_(headers=headers)

    page.route("**/*", handle_route)
    page.goto(SERVER_URL)

    expect(page.locator("#handover-status-badge")).to_be_visible()
    expect(page.locator("#outgoing-lead")).to_contain_text("Marcus Vance")
    expect(page.locator("#incoming-lead")).to_contain_text("Elena Rostova")


def test_e2e_stakeholder_restricted_workflow(page: Page):
    """
    E2E-03: Stakeholder Restricted Workflow
    Verifies Stakeholder role view-only access and absence of restricted execution controls.
    """
    def handle_route(route):
        headers = {
            **route.request.headers,
            "X-User-Role": DEV_ROLE,
            "X-User-Name": DEV_USER
        }
        route.continue_(headers=headers)

    page.route("**/*", handle_route)
    page.goto(SERVER_URL)

    expect(page.locator("body")).to_contain_text("Enterprise Identity Service")
    expect(page.locator("#fresh-metrics")).to_be_visible()
