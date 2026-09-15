"""
Dedicated Audit Tamper Detection and Hash Chain Verification Test Suite.
Verifies SHA-256 hash chaining integrity, canonical hash calculation, and automated tamper detection.
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db_models import Base, DBAuditEntry
from backend.repository import (
    seed_database_from_fixtures,
    add_audit_entry_db,
    verify_audit_trail_db,
    tamper_test_db
)

TEST_DB_FILE = "./test_audit_tamper.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"


@pytest.fixture(autouse=True)
def setup_and_teardown_tamper_db():
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)
    yield
    if os.path.exists(TEST_DB_FILE):
        os.remove(TEST_DB_FILE)


def test_sha256_audit_tamper_detection_on_persisted_database():
    """
    1. Initialize temporary SQLite database and seed initial audit entries.
    2. Add additional audit entry and verify SHA-256 chain is valid.
    3. Modify a persisted record's description in the database.
    4. Run verify_audit_trail_db and assert valid=False and first_invalid_record is flagged.
    """
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionMaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionMaker()

    seed_database_from_fixtures(db, force=True)

    add_audit_entry_db(
        db,
        actor="Elena Rostova",
        role="SRE / On-Call Specialist",
        action_type="TEST_AUDIT_ACTION",
        description="Valid audit record before tampering",
        metadata={"test": "tamper_test"}
    )

    # 1. Initial verification must be valid
    result_before = verify_audit_trail_db(db)
    assert result_before.valid is True
    assert result_before.first_invalid_record is None
    assert result_before.records_checked >= 4

    # 2. Tamper with record index 0
    tamper_res = tamper_test_db(db, record_index=0, actor="Elena Rostova", role="SRE / On-Call Specialist")
    assert tamper_res["status"] == "SUCCESS"

    # 3. Verification after tampering must detect failure
    result_after = verify_audit_trail_db(db)
    assert result_after.valid is False
    assert result_after.first_invalid_record == "AUD-5001"

    db.close()
    engine.dispose()
