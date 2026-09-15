from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


def new_id() -> str:
    return str(uuid.uuid4())


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # upload | youtube
    source_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ja", nullable=False)
    active_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pipeline_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    sample_rate: Mapped[int | None] = mapped_column(Integer)
    channels: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class PipelineArtifact(TimestampMixin, Base):
    __tablename__ = "pipeline_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    relative_path: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("uq_pipeline_artifact_kind_input", "project_id", "kind", "input_hash", unique=True),
    )


class ProcessingJob(TimestampMixin, Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), default="queued", nullable=False)
    progress_0_100: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="Đang chờ xử lý", nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_processing_jobs_queue", "status", "created_at"),)


class Speaker(TimestampMixin, Base):
    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#60a5fa")
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (Index("uq_speaker_project_label", "project_id", "label", unique=True),)


class Chunk(TimestampMixin, Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    speaker_id: Mapped[str | None] = mapped_column(
        ForeignKey("speakers.id", ondelete="SET NULL"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    vad_confidence: Mapped[float | None] = mapped_column()
    diarization_confidence: Mapped[float | None] = mapped_column()
    boundary_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint("start_ms >= 0", name="check_chunk_start_nonnegative"),
        CheckConstraint("end_ms > start_ms", name="check_chunk_end_after_start"),
        Index("ix_chunks_project_order", "project_id", "order_index", unique=True),
    )


class ChunkText(TimestampMixin, Base):
    __tablename__ = "chunk_texts"

    chunk_id: Mapped[str] = mapped_column(
        ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True
    )
    asr_raw: Mapped[str | None] = mapped_column(Text)
    asr_normalized: Mapped[str | None] = mapped_column(Text)
    reference_text: Mapped[str | None] = mapped_column(Text)
    reference_status: Mapped[str] = mapped_column(String(32), default="missing", nullable=False)
    furigana_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    furigana_status: Mapped[str] = mapped_column(String(32), default="missing", nullable=False)
    translation_vi: Mapped[str | None] = mapped_column(Text)
    translation_status: Mapped[str] = mapped_column(String(32), default="missing", nullable=False)
    translation_context_hash: Mapped[str | None] = mapped_column(String(64))
    asr_input_hash: Mapped[str | None] = mapped_column(String(64))
    furigana_input_hash: Mapped[str | None] = mapped_column(String(64))
    translation_input_hash: Mapped[str | None] = mapped_column(String(64))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Exercise(TimestampMixin, Base):
    __tablename__ = "exercises"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)  # full | cloze
    blank_spec_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    settings_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reference_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    is_difficult: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Attempt(TimestampMixin, Base):
    __tablename__ = "attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exercise_id: Mapped[str] = mapped_column(
        ForeignKey("exercises.id", ondelete="CASCADE"), index=True
    )
    answer_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    normalized_answer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    score: Mapped[float | None] = mapped_column()
    strict_score: Mapped[float | None] = mapped_column()
    diff_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    revealed_answer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)


class ModelRun(TimestampMixin, Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), index=True
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("processing_jobs.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_revision: Mapped[str | None] = mapped_column(String(255))
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    peak_vram_mb: Mapped[int | None] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)


class TranslationCache(TimestampMixin, Base):
    __tablename__ = "translation_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    translation_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)


class AppSetting(TimestampMixin, Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
