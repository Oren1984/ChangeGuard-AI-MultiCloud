from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from src.adapters.persistence.audit_repository_sqlalchemy import SqlAlchemyAuditRepository
from src.adapters.persistence.cab_repository_sqlalchemy import SqlAlchemyCabRepository
from src.adapters.persistence.change_repository_sqlalchemy import SqlAlchemyChangeRepository
from src.adapters.persistence.kill_switch_repository_sqlalchemy import SqlAlchemyKillSwitchRepository
from src.api.dependencies.db import get_db


def get_change_repo(session: Session = Depends(get_db)) -> SqlAlchemyChangeRepository:
    return SqlAlchemyChangeRepository(session)


def get_cab_repo(session: Session = Depends(get_db)) -> SqlAlchemyCabRepository:
    return SqlAlchemyCabRepository(session)


def get_audit_repo(session: Session = Depends(get_db)) -> SqlAlchemyAuditRepository:
    return SqlAlchemyAuditRepository(session)


def get_kill_switch_repo(session: Session = Depends(get_db)) -> SqlAlchemyKillSwitchRepository:
    return SqlAlchemyKillSwitchRepository(session)
