from __future__ import annotations

from jlpt_studio.api.schemas import ProjectCreate
from jlpt_studio.db.session import get_session_factory
from jlpt_studio.jobs.queue import enqueue_job, request_cancel
from jlpt_studio.services.projects import create_project


def test_queue_deduplicates_active_jobs_and_cancels_queued(isolated_db) -> None:
    with get_session_factory()() as session:
        project = create_project(session, ProjectCreate(title="Queue"))
        first = enqueue_job(session, project_id=project.id, job_type="process_project")
        duplicate = enqueue_job(session, project_id=project.id, job_type="process_project")
        assert first.id == duplicate.id
        cancelled = request_cancel(session, first.id)
        assert cancelled.status == "cancelled"
