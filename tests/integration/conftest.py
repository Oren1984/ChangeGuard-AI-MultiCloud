from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "CHANGEGUARD_DATABASE_URL", "postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard"
)

_APP_TABLES = (
    "gate_results",
    "routing_decisions",
    "ai_assessments",
    "risk_assessments",
    "cab_tickets",
    "audit_records",
    "kill_switch_state",
    "changes",
)


@pytest.fixture(scope="session")
def engine():
    return create_engine(DATABASE_URL, future=True, pool_pre_ping=True)


@pytest.fixture()
def db_session(engine) -> Session:
    session_factory = sessionmaker(bind=engine, future=True)
    session = session_factory()
    session.execute(text(f"TRUNCATE TABLE {', '.join(_APP_TABLES)} RESTART IDENTITY CASCADE"))
    session.commit()
    yield session
    session.close()
