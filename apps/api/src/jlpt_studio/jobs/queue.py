from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import JobRead
from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import ConflictError, NotFoundError
from jlpt_studio.db.models import ProcessingJob


def job_to_read(job: ProcessingJob) -> JobRead:
    return JobRead(
        id=job.id,
        project_id=job.project_id,
        type=job.type,
        status=job.status,
        stage=job.stage,
        progress_0_100=job.progress_0_100,
        message=job.message,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        error_detail=job.error_detail,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def enqueue_job(
    session: Session,
    *,
    project_id: str,
    job_type: str,
    payload: dict[str, Any] | None = None,
    input_hash: str | None = None,
    max_attempts: int = 2,
) -> ProcessingJob:
    active = session.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.project_id == project_id,
            ProcessingJob.type == job_type,
            ProcessingJob.status.in_(["queued", "running", "cancel_requested"]),
        )
        .order_by(ProcessingJob.created_at.desc())
    )
    if active is not None:
        return active
    job = ProcessingJob(
        project_id=project_id,
        type=job_type,
        payload_json=payload or {},
        input_hash=input_hash,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job_or_404(session: Session, job_id: str) -> ProcessingJob:
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise NotFoundError("Không tìm thấy job")
    return job


def recover_stale_jobs(session: Session, settings: Settings) -> int:
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.stale_job_seconds)
    stale = session.scalars(
        select(ProcessingJob).where(
            ProcessingJob.status == "running",
            ProcessingJob.heartbeat_at.is_not(None),
            ProcessingJob.heartbeat_at < cutoff,
        )
    ).all()
    for job in stale:
        job.status = "interrupted"
        job.stage = "interrupted"
        job.message = "Worker bị dừng; job có thể retry từ stage gần nhất"
    if stale:
        session.commit()
    return len(stale)


def claim_next_job(session: Session) -> ProcessingJob | None:
    """Claim a queued job with a conditional update suitable for SQLite workers."""
    candidate = session.scalar(
        select(ProcessingJob.id)
        .where(ProcessingJob.status == "queued")
        .order_by(ProcessingJob.created_at.asc())
        .limit(1)
    )
    if candidate is None:
        return None
    now = datetime.now(UTC)
    result = session.execute(
        update(ProcessingJob)
        .where(and_(ProcessingJob.id == candidate, ProcessingJob.status == "queued"))
        .values(
            status="running",
            stage="starting",
            message="Worker đang nhận job",
            started_at=now,
            heartbeat_at=now,
            attempt=ProcessingJob.attempt + 1,
            error_code=None,
            error_detail=None,
        )
    )
    session.commit()
    if result.rowcount != 1:
        return None
    return session.get(ProcessingJob, candidate)


def update_job_progress(
    session: Session,
    job: ProcessingJob,
    *,
    stage: str,
    progress: int,
    message: str,
) -> None:
    job.stage = stage
    job.progress_0_100 = max(0, min(100, progress))
    job.message = message
    job.heartbeat_at = datetime.now(UTC)
    session.commit()


def check_cancelled(session: Session, job_id: str) -> bool:
    job = session.get(ProcessingJob, job_id)
    return job is None or job.status == "cancel_requested"


def request_cancel(session: Session, job_id: str) -> ProcessingJob:
    job = get_job_or_404(session, job_id)
    if job.status not in {"queued", "running"}:
        raise ConflictError("JOB_NOT_CANCELLABLE", "Job này không thể hủy ở trạng thái hiện tại")
    if job.status == "queued":
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished_at = datetime.now(UTC)
        job.message = "Đã hủy trước khi worker nhận job"
    else:
        job.status = "cancel_requested"
        job.message = "Đã yêu cầu hủy job"
    session.commit()
    session.refresh(job)
    return job


def retry_job(session: Session, job_id: str) -> ProcessingJob:
    job = get_job_or_404(session, job_id)
    if job.status not in {"failed", "interrupted", "cancelled"}:
        raise ConflictError(
            "JOB_NOT_RETRYABLE", "Chỉ có thể chạy lại job lỗi, bị gián đoạn hoặc đã hủy"
        )
    if job.attempt >= job.max_attempts:
        job.max_attempts += 1
    job.status = "queued"
    job.stage = "queued"
    job.progress_0_100 = 0
    job.message = "Đang chờ chạy lại"
    job.error_code = None
    job.error_detail = None
    job.finished_at = None
    session.commit()
    session.refresh(job)
    return job


def finish_job(session: Session, job: ProcessingJob, message: str = "Hoàn thành") -> None:
    job.status = "succeeded"
    job.stage = "completed"
    job.progress_0_100 = 100
    job.message = message
    job.heartbeat_at = datetime.now(UTC)
    job.finished_at = datetime.now(UTC)
    session.commit()


def cancel_job(session: Session, job: ProcessingJob) -> None:
    job.status = "cancelled"
    job.stage = "cancelled"
    job.message = "Đã hủy"
    job.finished_at = datetime.now(UTC)
    session.commit()


def fail_job(session: Session, job: ProcessingJob, code: str, detail: str) -> None:
    job.status = "failed"
    job.stage = "failed"
    job.message = "Job xử lý thất bại"
    job.error_code = code
    job.error_detail = detail[:4000]
    job.finished_at = datetime.now(UTC)
    session.commit()
