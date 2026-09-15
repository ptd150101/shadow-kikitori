from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ApiError(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] | None = None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source_type: Literal["upload", "youtube"] = "upload"
    source_url: str | None = None
    pipeline_config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def source_url_for_youtube(self) -> ProjectCreate:
        if self.source_type == "youtube" and not self.source_url:
            raise ValueError("source_url is required for YouTube projects")
        return self


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    pipeline_config: dict[str, Any] | None = None


class ProjectRead(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: str | None
    status: str
    language: str
    active_revision: int
    last_opened_at: datetime | None
    pipeline_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    duration_ms: int | None = None
    chunk_count: int = 0


class JobRead(BaseModel):
    id: str
    project_id: str
    type: str
    status: str
    stage: str
    progress_0_100: int
    message: str
    attempt: int
    max_attempts: int
    error_code: str | None
    error_detail: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class SpeakerRead(BaseModel):
    id: str
    label: str
    display_name: str
    color: str
    is_manual: bool


class FuriganaToken(BaseModel):
    surface: str
    reading: str | None = None
    ruby: bool = False
    part_of_speech: str | None = None


class ChunkTextRead(BaseModel):
    asr_raw: str | None = None
    asr_normalized: str | None = None
    reference_text: str | None = None
    reference_status: str
    furigana: list[FuriganaToken] | None = None
    furigana_status: str
    translation_vi: str | None = None
    translation_status: str


class ChunkRead(BaseModel):
    id: str
    project_id: str
    speaker_id: str | None
    order_index: int
    start_ms: int
    end_ms: int
    source: str
    status: str
    boundary_revision: int
    speaker: SpeakerRead | None = None
    text: ChunkTextRead | None = None


class ChunkUpdate(BaseModel):
    start_ms: int | None = Field(default=None, ge=0)
    end_ms: int | None = Field(default=None, gt=0)
    speaker_id: str | None = None
    status: str | None = None
    expected_boundary_revision: int | None = Field(default=None, ge=1)


class ChunkReorderRequest(BaseModel):
    ordered_chunk_ids: list[str] = Field(min_length=1, max_length=200)
    expected_project_revision: int | None = Field(default=None, ge=1)


class SpeakerUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class SpeakerCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    color: str = Field(default="#60a5fa", pattern=r"^#[0-9a-fA-F]{6}$")


class SplitChunkRequest(BaseModel):
    at_ms: int = Field(ge=1)
    expected_boundary_revision: int | None = Field(default=None, ge=1)


class MergeChunksRequest(BaseModel):
    chunk_ids: list[str] = Field(min_length=2, max_length=100)
    expected_project_revision: int | None = Field(default=None, ge=1)


class ReferenceUpdate(BaseModel):
    reference_text: str = Field(min_length=1)
    confirm: bool = True


class TranslationUpdate(BaseModel):
    translation_vi: str = Field(min_length=1)
    confirm: bool = True


class FuriganaUpdate(BaseModel):
    furigana: list[FuriganaToken]
    confirm: bool = True


class ReprocessRequest(BaseModel):
    stages: list[Literal["vad", "diarization", "chunking", "asr", "furigana", "translation"]] = (
        Field(default_factory=lambda: ["asr", "furigana", "translation"])
    )
    chunk_ids: list[str] | None = Field(default=None, max_length=200)


class TranslateBatchRequest(BaseModel):
    chunk_ids: list[str] | None = Field(default=None, max_length=200)
    batch_size: int = Field(default=10, ge=1, le=50)
    context_size: int = Field(default=4, ge=0, le=12)


class ProcessProjectRequest(BaseModel):
    stages: list[str] | None = None
    force: bool = False
    segmentation_preset: Literal["fewer", "balanced", "short"] = "balanced"
    num_speakers: int | None = Field(default=None, ge=1, le=10)
    vad_threshold: float | None = Field(default=None, ge=0.05, le=0.99)
    min_speech_ms: int | None = Field(default=None, ge=50, le=5000)
    min_silence_ms: int | None = Field(default=None, ge=50, le=10000)
    speech_pad_ms: int | None = Field(default=None, ge=0, le=2000)
    merge_gap_ms: int | None = Field(default=None, ge=0, le=5000)
    target_chunk_ms: int | None = Field(default=None, ge=1000, le=28000)
    max_chunk_ms: int | None = Field(default=None, ge=1500, le=28000)


class YouTubeImportRequest(BaseModel):
    url: str = Field(min_length=10, max_length=2048)


class CreateExercisesRequest(BaseModel):
    mode: Literal["full", "cloze"]
    chunk_ids: list[str] | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class ExerciseRead(BaseModel):
    id: str
    project_id: str
    chunk_id: str
    mode: str
    blank_spec: dict[str, Any]
    settings: dict[str, Any]
    reference_revision: int
    status: str
    is_difficult: bool
    reference_status: str = "missing"
    chunk: ChunkRead | None = None


class AnswerBundle(BaseModel):
    reference_text: str
    furigana: list[FuriganaToken] | None = None
    translation_vi: str | None = None
    cloze_expected: list[str] = Field(default_factory=list)
    reference_confirmed: bool = False


class ExerciseAnswerRead(BaseModel):
    exercise_id: str
    chunk_id: str
    mode: Literal["full", "cloze"]
    reference_text: str
    furigana: list[FuriganaToken] | None = None
    translation_vi: str | None = None
    blank_spec: dict[str, Any] = Field(default_factory=dict)
    reference_confirmed: bool = False


class ExerciseUpdate(BaseModel):
    blank_spec: dict[str, Any] | None = None
    is_difficult: bool | None = None


class AttemptCreate(BaseModel):
    answer_text: str = ""
    blank_answers: list[str] | None = None
    revealed_answer: bool = False
    duration_ms: int | None = Field(default=None, ge=0)


class AttemptRead(BaseModel):
    id: str
    exercise_id: str
    answer_text: str
    score: float | None
    strict_score: float | None
    diff: list[dict[str, Any]]
    revealed_answer: bool
    duration_ms: int | None
    created_at: datetime
    answer: AnswerBundle | None = None


class CapabilityRead(BaseModel):
    ffmpeg: bool
    ffprobe: bool
    ytdlp: bool
    cuda_available: bool
    data_dir: str
    platform: str | None = None
    max_upload_bytes: int | None = None
    max_duration_seconds: int | None = None


class ProviderStatus(BaseModel):
    name: str
    ready: bool
    detail: str


class AppSettingsRead(BaseModel):
    ffmpeg_path: str
    ffprobe_path: str
    ytdlp_path: str
    audio8_model_id: str
    audio8_revision: str | None
    pyannote_model_path: str | None
    device: str
    llm_mode: str
    llm_base_url: str
    llm_model: str
    llm_executable: str | None
    llm_model_path: str | None
    audio8_max_seconds: int = 28


class AppSettingsUpdate(BaseModel):
    ffmpeg_path: str | None = None
    ffprobe_path: str | None = None
    ytdlp_path: str | None = None
    device: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    audio8_model_id: str | None = None
    audio8_revision: str | None = None
    pyannote_model_path: str | None = None
    hf_token: str | None = None
    llm_mode: Literal["external", "managed"] | None = None
    llm_executable: str | None = None
    llm_model_path: str | None = None
    llm_port: int | None = Field(default=None, ge=1, le=65535)

    @field_validator("llm_base_url")
    @classmethod
    def normalize_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else value


class TimelineSnapshotRead(BaseModel):
    project_id: str
    revision: int
    duration_ms: int | None
    chunks: list[ChunkRead]


class MediaAssetRead(BaseModel):
    id: str
    kind: str
    original_name: str | None
    mime_type: str | None
    size_bytes: int
    duration_ms: int | None
    sample_rate: int | None
    channels: int | None
    sha256: str | None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentationMetricsRead(BaseModel):
    project_id: str
    chunk_count: int
    speech_coverage_ms: int
    silence_coverage_ms: int
    mean_chunk_ms: float
    median_chunk_ms: float
    p95_chunk_ms: float
    short_chunk_count: int
    over_target_count: int
    max_chunk_ms: int
    vad_region_count: int = 0
    speaker_count: int = 0


class ExportRequest(BaseModel):
    include_audio: bool = False
    include_attempts: bool = True


class CleanupRead(BaseModel):
    removed_files: int
    removed_bytes: int
    removed_cache_files: int
