from __future__ import annotations

from sqlalchemy import select

from .base import Base
from .models import Project  # noqa: F401 - imports all model metadata through module evaluation
from .session import get_engine, get_session_factory


def initialize_database() -> None:
    """Create tables for first-run local installs.

    Alembic remains the normal migration route. create_all makes a fresh local
    install usable before an explicit migration command is run.
    """
    Base.metadata.create_all(get_engine())


def database_is_reachable() -> bool:
    with get_session_factory()() as session:
        session.execute(select(Project.id).limit(1))
    return True
