from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import ProjectCreate, ProjectRead, ProjectUpdate
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import Chunk, MediaAsset, Project


def project_to_read(session: Session, project: Project) -> ProjectRead:
    duration_ms = session.scalar(
        select(MediaAsset.duration_ms).where(
            MediaAsset.project_id == project.id, MediaAsset.kind == "playback"
        )
    )
    if duration_ms is None:
        duration_ms = session.scalar(
            select(MediaAsset.duration_ms).where(
                MediaAsset.project_id == project.id, MediaAsset.kind == "source"
            )
        )
    chunk_count = (
        session.scalar(select(func.count(Chunk.id)).where(Chunk.project_id == project.id)) or 0
    )
    return ProjectRead(
        id=project.id,
        title=project.title,
        source_type=project.source_type,
        source_url=project.source_url,
        status=project.status,
        language=project.language,
        active_revision=project.active_revision,
        last_opened_at=project.last_opened_at,
        pipeline_config=project.pipeline_config_json,
        created_at=project.created_at,
        updated_at=project.updated_at,
        duration_ms=duration_ms,
        chunk_count=chunk_count,
    )


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project = Project(
        title=payload.title.strip(),
        source_type=payload.source_type,
        source_url=payload.source_url,
        pipeline_config_json=payload.pipeline_config,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_project_or_404(session: Session, project_id: str) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise NotFoundError("Không tìm thấy project")
    return project


def list_projects(session: Session) -> list[ProjectRead]:
    projects = session.scalars(
        select(Project).order_by(Project.last_opened_at.desc(), Project.updated_at.desc())
    ).all()
    return [project_to_read(session, project) for project in projects]


def update_project(session: Session, project_id: str, payload: ProjectUpdate) -> Project:
    project = get_project_or_404(session, project_id)
    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.pipeline_config is not None:
        project.pipeline_config_json = payload.pipeline_config
    project.active_revision += 1
    session.commit()
    session.refresh(project)
    return project


def mark_project_opened(session: Session, project: Project) -> None:
    project.last_opened_at = datetime.now(UTC)
    session.commit()


def delete_project(session: Session, project_id: str) -> Project:
    project = get_project_or_404(session, project_id)
    session.delete(project)
    session.commit()
    return project
