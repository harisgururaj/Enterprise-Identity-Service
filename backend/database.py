"""
SQLite Database Connection and Session Management for Enterprise Identity Service.
Supports DATABASE_URL environment variable (default: sqlite:///./identity_workspace.db).
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./identity_workspace.db")

# For SQLite, connect_args check_same_thread=False allows multi-threaded FastAPI requests
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initializes schema tables cleanly."""
    from backend.db_models import (  # noqa: F401
        DBIncidentWorkspace, DBIncidentNote, DBChatExcerpt, DBDashboardMetric,
        DBOwnershipChange, DBActionLog, DBHypothesis, DBEvidence,
        DBChangeReviewRequest, DBSourceResilienceItem, DBAuditEntry,
        DBFreshnessStatus, DBStakeholderTask
    )
    Base.metadata.create_all(bind=engine)
