from __future__ import annotations

import logging
import signal
import time

from jlpt_studio.core.config import get_settings
from jlpt_studio.core.errors import StudioError
from jlpt_studio.core.logging import configure_logging
from jlpt_studio.db.init import initialize_database
from jlpt_studio.db.models import Project
from jlpt_studio.db.session import get_session_factory
from jlpt_studio.jobs.queue import (
    cancel_job,
    claim_next_job,
    fail_job,
    finish_job,
    recover_stale_jobs,
)
from jlpt_studio.pipeline.orchestrator import JobCancelled, ProjectPipeline
from jlpt_studio.services.settings import get_runtime_settings

logger = logging.getLogger(__name__)
_running = True


def _stop(_signum, _frame) -> None:  # type: ignore[no-untyped-def]
    global _running
    _running = False


def run_worker() -> None:
    settings = get_settings()
    configure_logging(settings)
    initialize_database()
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    factory = get_session_factory()
    with factory() as session:
        count = recover_stale_jobs(session, settings)
        if count:
            logger.info("recovered %s stale jobs", count)
    logger.info("worker started")
    while _running:
        with factory() as session:
            job = claim_next_job(session)
            if job is None:
                time.sleep(settings.worker_poll_seconds)
                continue
            logger.info("running job=%s type=%s", job.id, job.type)
            try:
                if job.type != "process_project":
                    raise StudioError("UNKNOWN_JOB_TYPE", f"Không hỗ trợ job type: {job.type}")
                ProjectPipeline(session, get_runtime_settings(session, settings), job).run()
                finish_job(session, job)
                logger.info("job succeeded=%s", job.id)
            except JobCancelled:
                session.rollback()
                cancel_job(session, job)
                project = session.get(Project, job.project_id)
                if project:
                    project.status = "imported"
                    session.commit()
                logger.info("job cancelled=%s", job.id)
            except StudioError as error:
                session.rollback()
                fail_job(session, job, error.code, error.message)
                project = session.get(Project, job.project_id)
                if project:
                    project.status = "error"
                    session.commit()
                logger.exception("job failed=%s code=%s", job.id, error.code)
            except Exception as error:  # noqa: BLE001
                session.rollback()
                fail_job(session, job, "UNEXPECTED_ERROR", str(error))
                project = session.get(Project, job.project_id)
                if project:
                    project.status = "error"
                    session.commit()
                logger.exception("job failed unexpectedly=%s", job.id)
    logger.info("worker stopped")


if __name__ == "__main__":
    run_worker()
