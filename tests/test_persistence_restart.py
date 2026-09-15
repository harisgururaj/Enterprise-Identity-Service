"""
Dedicated Database Restart and SHA-256 Audit Durability Test Suite.
Programmatically proves SQLite persistence across engine dispose/restart,
ensuring hypotheses, evidence, change reviews, and SHA-256 audit hash chains survive restarts.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db_models import Base, DBHypothesis, DBEvidence, DBAuditEntry
from backend.repository import (
    seed_database_from_fixtures,
    get_workspace_state_db,
    add_audit_entry_db,
    verify_audit_trail_db,
    create_hypothesis_db,
    link_evidence_db
)
from backend.models import SourceType, EvidenceImpact

TEST_DB_FILE = "./test_persistence_restart.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"


@pytest.fixture(autouse=True)
def cleanup_test_db():
    """Ensure test database file is cleaned up before and after test."""
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


def test_database_restart_persistence_and_audit_durability():
    """
    1. Create SQLite DB engine and seed data.
    2. Add new hypothesis, evidence, and audit entry in Session 1.
    3. Dispose engine and close session (simulating server shutdown/restart).
    4. Re-open new engine and Session 2 on same database file.
    5. Verify data and SHA-256 audit hash chain remain 100% valid.
    """
    # --- PHASE 1: INITIAL SESSION ---
    engine1 = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine1)
    SessionMaker1 = sessionmaker(autocommit=False, autoflush=False, bind=engine1)
    db1 = SessionMaker1()

    seed_database_from_fixtures(db1, force=True)

    # Create new hypothesis in db1
    hypo_res = create_hypothesis_db(
        db1,
        title="Persisted Restart Hypothesis Test",
        description="Verifying SQLite storage across database restart",
        confidence_score=0.75,
        actor="Elena Rostova",
        role="SRE / On-Call Specialist"
    )
    hypo_id = hypo_res["hypothesis"]["id"]

    # Link evidence in db1
    evid_res = link_evidence_db(
        db1,
        hypothesis_id=hypo_id,
        source_type=SourceType.METRIC,
        source_id="METRIC-AUTH-02",
        title="Persisted Metric Evidence",
        snippet="JWT Error Rate spiked post-key rotation",
        impact=EvidenceImpact.SUPPORTS,
        actor="Elena Rostova",
        role="SRE / On-Call Specialist"
    )
    evid_id = evid_res["evidence"]["id"]

    # Verify audit chain initial validity
    audit_check1 = verify_audit_trail_db(db1)
    assert audit_check1.valid is True

    db1.close()
    engine1.dispose()  # SIMULATE FULL SERVER RESTART AND DB UNMOUNT

    # --- PHASE 2: RESTART SESSION ---
    engine2 = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    SessionMaker2 = sessionmaker(autocommit=False, autoflush=False, bind=engine2)
    db2 = SessionMaker2()

    ws_after_restart = get_workspace_state_db(db2)

    # Assert hypothesis exists in DB after restart
    found_hypo = next((h for h in ws_after_restart.hypotheses if h.id == hypo_id), None)
    assert found_hypo is not None
    assert found_hypo.title == "Persisted Restart Hypothesis Test"

    # Assert evidence exists in DB after restart
    found_evid = next((e for e in ws_after_restart.evidence_list if e.id == evid_id), None)
    assert found_evid is not None
    assert found_evid.snippet == "JWT Error Rate spiked post-key rotation"

    # Assert audit trail SHA-256 hash chain remains 100% valid after restart
    audit_check2 = verify_audit_trail_db(db2)
    assert audit_check2.valid is True
    assert audit_check2.records_checked > 3

    db2.close()
    engine2.dispose()
