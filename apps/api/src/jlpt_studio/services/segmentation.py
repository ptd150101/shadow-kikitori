from __future__ import annotations

from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import SegmentationMetricsRead
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import Chunk, MediaAsset, PipelineArtifact, Project, Speaker


def segmentation_metrics(session: Session, project_id: str) -> SegmentationMetricsRead:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Không tìm thấy project")
    chunks = session.scalars(select(Chunk).where(Chunk.project_id == project_id).order_by(Chunk.order_index)).all()
    duration = session.scalar(select(MediaAsset.duration_ms).where(MediaAsset.project_id == project_id, MediaAsset.kind == "playback")) or 0
    durations = [max(0, chunk.end_ms - chunk.start_ms) for chunk in chunks]
    speech = sum(durations)
    silence = max(0, int(duration) - speech)
    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, round(len(ordered) * 0.95) - 1)] if ordered else 0
    vad_count = 0
    artifact = session.scalar(select(PipelineArtifact).where(PipelineArtifact.project_id == project_id, PipelineArtifact.kind == "vad").order_by(PipelineArtifact.updated_at.desc()))
    if artifact:
        vad_count = len(artifact.data_json.get("regions", []))
    speaker_count = len(session.scalars(select(Speaker).where(Speaker.project_id == project_id)).all())
    return SegmentationMetricsRead(
        project_id=project_id,
        chunk_count=len(chunks),
        speech_coverage_ms=speech,
        silence_coverage_ms=silence,
        mean_chunk_ms=round(speech / len(durations), 1) if durations else 0,
        median_chunk_ms=round(float(median(durations)), 1) if durations else 0,
        p95_chunk_ms=float(p95),
        short_chunk_count=sum(value < 1200 for value in durations),
        over_target_count=sum(value > 10000 for value in durations),
        max_chunk_ms=max(durations, default=0),
        vad_region_count=vad_count,
        speaker_count=speaker_count,
    )
