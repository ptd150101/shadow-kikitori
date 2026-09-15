from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import (
    AppSettingsRead,
    AppSettingsUpdate,
    AttemptCreate,
    AttemptRead,
    CapabilityRead,
    ChunkRead,
    ChunkReorderRequest,
    ChunkUpdate,
    CleanupRead,
    CreateExercisesRequest,
    ExerciseAnswerRead,
    ExerciseRead,
    ExerciseUpdate,
    ExportRequest,
    FuriganaUpdate,
    JobRead,
    MediaAssetRead,
    MergeChunksRequest,
    ProcessProjectRequest,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProviderStatus,
    ReferenceUpdate,
    ReprocessRequest,
    SegmentationMetricsRead,
    SpeakerCreate,
    SpeakerRead,
    SpeakerUpdate,
    SplitChunkRequest,
    TimelineSnapshotRead,
    TranslateBatchRequest,
    TranslationUpdate,
    YouTubeImportRequest,
)
from jlpt_studio.core.config import Settings, get_settings
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import MediaAsset
from jlpt_studio.db.session import get_session
from jlpt_studio.jobs.queue import (
    enqueue_job,
    get_job_or_404,
    job_to_read,
    request_cancel,
    retry_job,
)
from jlpt_studio.media.ffmpeg import FfmpegRunner
from jlpt_studio.media.importer import MediaImporter
from jlpt_studio.services.chunks import (
    chunk_to_read,
    create_speaker,
    delete_chunk,
    list_chunks,
    list_practice_chunks,
    list_speakers,
    merge_chunks,
    reorder_chunks,
    split_chunk,
    timeline_snapshot,
    update_chunk,
    update_speaker,
    upsert_furigana,
    upsert_reference,
)
from jlpt_studio.services.exports import cleanup_project, export_project
from jlpt_studio.services.model_health import provider_status
from jlpt_studio.services.paths import project_dir, resolve_relative_project_path
from jlpt_studio.services.practice import (
    _exercise_to_read,
    exercise_answer,
    generate_exercises,
    list_exercises,
    project_stats,
    submit_attempt,
    update_exercise,
)
from jlpt_studio.services.projects import (
    create_project,
    delete_project,
    get_project_or_404,
    list_projects,
    mark_project_opened,
    project_to_read,
    update_project,
)
from jlpt_studio.services.segmentation import segmentation_metrics
from jlpt_studio.services.settings import (
    get_runtime_settings,
    settings_to_read,
    update_runtime_settings,
)
from jlpt_studio.services.translation import translate_project_chunks, upsert_translation

router = APIRouter(prefix="/api")


def db_session() -> Session:
    yield from get_session()


def runtime_settings(session: Session = Depends(db_session)) -> Settings:
    return get_runtime_settings(session, get_settings())


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/system/capabilities", response_model=CapabilityRead)
def system_capabilities(settings: Settings = Depends(runtime_settings)) -> CapabilityRead:
    runner = FfmpegRunner(settings)
    cuda_available = False
    try:
        import torch

        cuda_available = bool(torch.cuda.is_available())
    except ImportError:
        pass
    return CapabilityRead(
        ffmpeg=runner.has_ffmpeg(),
        ffprobe=runner.has_ffprobe(),
        ytdlp=shutil.which(settings.ytdlp_path) is not None,
        cuda_available=cuda_available,
        data_dir=str(settings.resolved_data_dir),
        platform=__import__("platform").platform(),
        max_upload_bytes=settings.max_upload_bytes,
        max_duration_seconds=settings.max_duration_seconds,
    )


@router.get("/models/status", response_model=list[ProviderStatus])
def model_status(settings: Settings = Depends(runtime_settings)) -> list[ProviderStatus]:
    return [ProviderStatus(**item) for item in provider_status(settings)]


@router.post("/models/{provider}/check", response_model=ProviderStatus)
def check_model(provider: str, settings: Settings = Depends(runtime_settings)) -> ProviderStatus:
    aliases = {"audio8": "Audio8 ASR", "asr": "Audio8 ASR", "pyannote": "Community-1 diarization", "community-1": "Community-1 diarization", "gemma": "Gemma 4 translation", "llm": "Gemma 4 translation"}
    name = aliases.get(provider.lower(), provider)
    for item in provider_status(settings):
        if item["name"] == name:
            return ProviderStatus(**item)
    return ProviderStatus(name=provider, ready=False, detail="Provider không được hỗ trợ")


@router.get("/settings", response_model=AppSettingsRead)
def read_settings(settings: Settings = Depends(runtime_settings)) -> AppSettingsRead:
    return settings_to_read(settings)


@router.put("/settings", response_model=AppSettingsRead)
def write_settings(
    payload: AppSettingsUpdate,
    session: Session = Depends(db_session),
) -> AppSettingsRead:
    settings = update_runtime_settings(session, get_settings(), payload)
    return settings_to_read(settings)


@router.post("/projects", response_model=ProjectRead, status_code=201)
def post_project(payload: ProjectCreate, session: Session = Depends(db_session)) -> ProjectRead:
    project = create_project(session, payload)
    project_dir(get_settings(), project.id)
    return project_to_read(session, project)


@router.get("/projects", response_model=list[ProjectRead])
def get_projects(session: Session = Depends(db_session)) -> list[ProjectRead]:
    return list_projects(session)


@router.get("/projects/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(db_session)) -> ProjectRead:
    project = get_project_or_404(session, project_id)
    mark_project_opened(session, project)
    return project_to_read(session, project)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
def patch_project(
    project_id: str, payload: ProjectUpdate, session: Session = Depends(db_session)
) -> ProjectRead:
    return project_to_read(session, update_project(session, project_id, payload))


@router.delete("/projects/{project_id}", status_code=204)
def remove_project(project_id: str, session: Session = Depends(db_session)) -> None:
    project = delete_project(session, project_id)
    shutil.rmtree(project_dir(get_settings(), project.id), ignore_errors=True)


@router.post("/projects/{project_id}/media/upload", status_code=201)
def upload_media(
    project_id: str,
    file: UploadFile = File(...),
    session: Session = Depends(db_session),
    settings: Settings = Depends(runtime_settings),
) -> dict[str, object]:
    project = get_project_or_404(session, project_id)
    importer = MediaImporter(settings)
    imported = importer.import_upload(project, file)
    asset = importer.persist_source_asset(session, project, imported)
    return {"asset_id": asset.id, "duration_ms": asset.duration_ms, "sha256": asset.sha256, "original_name": asset.original_name, "mime_type": asset.mime_type, "size_bytes": asset.size_bytes, "sample_rate": asset.sample_rate, "channels": asset.channels, "metadata": asset.metadata_json}


@router.post("/projects/{project_id}/media/youtube", status_code=201)
def import_youtube(
    project_id: str,
    payload: YouTubeImportRequest,
    session: Session = Depends(db_session),
    settings: Settings = Depends(runtime_settings),
) -> dict[str, object]:
    project = get_project_or_404(session, project_id)
    imported = MediaImporter(settings).import_youtube(project, payload.url)
    asset = MediaImporter(settings).persist_source_asset(session, project, imported)
    project.source_type = "youtube"
    project.source_url = payload.url
    session.commit()
    return {"asset_id": asset.id, "duration_ms": asset.duration_ms, "sha256": asset.sha256, "original_name": asset.original_name, "metadata": asset.metadata_json}


@router.get("/projects/{project_id}/media", response_model=list[MediaAssetRead])
def get_media_assets(project_id: str, session: Session = Depends(db_session)) -> list[MediaAssetRead]:
    get_project_or_404(session, project_id)
    assets = session.scalars(select(MediaAsset).where(MediaAsset.project_id == project_id).order_by(MediaAsset.kind)).all()
    return [MediaAssetRead(id=item.id, kind=item.kind, original_name=item.original_name, mime_type=item.mime_type, size_bytes=item.size_bytes, duration_ms=item.duration_ms, sample_rate=item.sample_rate, channels=item.channels, sha256=item.sha256, metadata=item.metadata_json) for item in assets]


@router.get("/projects/{project_id}/media/stream")
def stream_media(project_id: str, request: Request, session: Session = Depends(db_session)) -> Response:
    asset = session.scalar(
        select(MediaAsset).where(MediaAsset.project_id == project_id, MediaAsset.kind == "playback")
    )
    if not asset:
        raise NotFoundError("Project chưa có audio playback")
    path = resolve_relative_project_path(get_settings(), asset.relative_path)
    if not path.exists():
        raise NotFoundError("Không tìm thấy file audio playback")
    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type="audio/ogg", filename="audio.ogg", headers={"Accept-Ranges": "bytes"})
    try:
        unit, raw_range = range_header.split("=", 1)
        if unit != "bytes":
            raise ValueError
        raw_start, raw_end = (raw_range.split("-", 1) + [""])[:2]
        start = int(raw_start) if raw_start else max(0, file_size - int(raw_end))
        end = int(raw_end) if raw_end else file_size - 1
        if start < 0 or start >= file_size or end < start:
            raise ValueError
        end = min(end, file_size - 1)
    except (ValueError, TypeError):
        return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
    length = end - start + 1
    def iterator():
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining:
                block = handle.read(min(1024 * 1024, remaining))
                if not block:
                    return
                remaining -= len(block)
                yield block
    return StreamingResponse(iterator(), status_code=206, media_type="audio/ogg", headers={"Accept-Ranges": "bytes", "Content-Range": f"bytes {start}-{end}/{file_size}", "Content-Length": str(length)})


@router.get("/projects/{project_id}/waveform")
def get_waveform(project_id: str, resolution: int = Query(default=4000, ge=128, le=20000), session: Session = Depends(db_session)) -> dict[str, object]:
    asset = session.scalar(
        select(MediaAsset).where(MediaAsset.project_id == project_id, MediaAsset.kind == "waveform")
    )
    if not asset:
        raise NotFoundError("Project chưa có waveform")
    path = resolve_relative_project_path(get_settings(), asset.relative_path)
    if not path.exists():
        raise NotFoundError("Không tìm thấy waveform")
    data = json.loads(path.read_text(encoding="utf-8"))
    peaks = data.get("peaks", [])
    if len(peaks) > resolution:
        stride = max(1, (len(peaks) + resolution - 1) // resolution)
        data["peaks"] = peaks[::stride]
        data["points"] = len(data["peaks"])
    return data


@router.post("/projects/{project_id}/process", response_model=JobRead, status_code=202)
def process_project(
    project_id: str,
    payload: ProcessProjectRequest,
    session: Session = Depends(db_session),
) -> JobRead:
    project = get_project_or_404(session, project_id)
    has_source = session.scalar(
        select(MediaAsset.id).where(
            MediaAsset.project_id == project.id, MediaAsset.kind == "source"
        )
    )
    if not has_source:
        raise NotFoundError("Hãy upload audio hoặc import YouTube trước khi xử lý")
    job = enqueue_job(
        session,
        project_id=project.id,
        job_type="process_project",
        payload={
            "stages": payload.stages
            or ["vad", "diarization", "chunking", "asr", "furigana", "translation"],
            "force": payload.force,
            "segmentation_preset": payload.segmentation_preset,
            "num_speakers": payload.num_speakers,
            **{key: value for key, value in payload.model_dump().items() if key not in {"stages", "force", "segmentation_preset", "num_speakers"} and value is not None},
        },
    )
    project.status = "processing"
    session.commit()
    return job_to_read(job)


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(db_session)) -> JobRead:
    return job_to_read(get_job_or_404(session, job_id))


@router.post("/jobs/{job_id}/cancel", response_model=JobRead)
def cancel_processing_job(job_id: str, session: Session = Depends(db_session)) -> JobRead:
    return job_to_read(request_cancel(session, job_id))


@router.post("/jobs/{job_id}/retry", response_model=JobRead)
def retry_processing_job(job_id: str, session: Session = Depends(db_session)) -> JobRead:
    return job_to_read(retry_job(session, job_id))


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request) -> StreamingResponse:
    get_settings()  # Force configuration validation before holding the SSE connection.

    async def event_stream() -> AsyncIterator[str]:
        last_payload: str | None = None
        while True:
            if await request.is_disconnected():
                return
            session = next(get_session())
            try:
                job = get_job_or_404(session, job_id)
                payload = job_to_read(job).model_dump(mode="json")
            finally:
                session.close()
            encoded = json.dumps(payload, ensure_ascii=False)
            if encoded != last_payload:
                yield f"event: job\ndata: {encoded}\n\n"
                last_payload = encoded
            if payload["status"] in {"succeeded", "failed", "cancelled"}:
                return
            await asyncio.sleep(0.8)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/projects/{project_id}/chunks", response_model=list[ChunkRead])
def get_chunks(project_id: str, session: Session = Depends(db_session)) -> list[ChunkRead]:
    return list_chunks(session, project_id)


@router.get("/projects/{project_id}/practice-chunks", response_model=list[ChunkRead])
def get_practice_chunks(project_id: str, session: Session = Depends(db_session)) -> list[ChunkRead]:
    return list_practice_chunks(session, project_id)


@router.get("/projects/{project_id}/timeline", response_model=TimelineSnapshotRead)
def get_timeline(project_id: str, session: Session = Depends(db_session)) -> TimelineSnapshotRead:
    return timeline_snapshot(session, project_id)


@router.get("/projects/{project_id}/speakers", response_model=list[SpeakerRead])
def get_speakers(project_id: str, session: Session = Depends(db_session)) -> list[SpeakerRead]:
    return list_speakers(session, project_id)


@router.post("/projects/{project_id}/speakers", response_model=SpeakerRead, status_code=201)
def post_speaker(project_id: str, payload: SpeakerCreate, session: Session = Depends(db_session)) -> SpeakerRead:
    speaker = create_speaker(session, project_id, payload.label, payload.display_name, payload.color)
    return SpeakerRead(id=speaker.id, label=speaker.label, display_name=speaker.display_name, color=speaker.color, is_manual=speaker.is_manual)


@router.patch("/speakers/{speaker_id}", response_model=SpeakerRead)
def patch_speaker(speaker_id: str, payload: SpeakerUpdate, session: Session = Depends(db_session)) -> SpeakerRead:
    speaker = update_speaker(session, speaker_id, payload)
    return SpeakerRead(id=speaker.id, label=speaker.label, display_name=speaker.display_name, color=speaker.color, is_manual=speaker.is_manual)


@router.patch("/chunks/{chunk_id}", response_model=ChunkRead)
def patch_chunk(
    chunk_id: str, payload: ChunkUpdate, session: Session = Depends(db_session)
) -> ChunkRead:
    return chunk_to_read(session, update_chunk(session, chunk_id, payload))


@router.post("/projects/{project_id}/chunks/reorder", response_model=list[ChunkRead])
def post_reorder_chunks(project_id: str, payload: ChunkReorderRequest, session: Session = Depends(db_session)) -> list[ChunkRead]:
    return [chunk_to_read(session, item) for item in reorder_chunks(session, project_id, payload.ordered_chunk_ids, payload.expected_project_revision)]


@router.delete("/chunks/{chunk_id}", status_code=204)
def remove_chunk(chunk_id: str, expected_project_revision: int | None = Query(default=None, ge=1), session: Session = Depends(db_session)) -> None:
    delete_chunk(session, chunk_id, expected_project_revision)


@router.post("/chunks/{chunk_id}/split", response_model=list[ChunkRead])
def post_split_chunk(
    chunk_id: str, payload: SplitChunkRequest, session: Session = Depends(db_session)
) -> list[ChunkRead]:
    left, right = split_chunk(session, chunk_id, payload.at_ms, payload.expected_boundary_revision)
    return [chunk_to_read(session, left), chunk_to_read(session, right)]


@router.post("/chunks/merge", response_model=ChunkRead)
def post_merge_chunks(
    payload: MergeChunksRequest, session: Session = Depends(db_session)
) -> ChunkRead:
    return chunk_to_read(
        session, merge_chunks(session, payload.chunk_ids, payload.expected_project_revision)
    )


@router.put("/chunks/{chunk_id}/reference", response_model=ChunkRead)
def put_chunk_reference(
    chunk_id: str, payload: ReferenceUpdate, session: Session = Depends(db_session)
) -> ChunkRead:
    upsert_reference(session, chunk_id, payload.reference_text, payload.confirm)
    from jlpt_studio.services.chunks import get_chunk_or_404
    return chunk_to_read(session, get_chunk_or_404(session, chunk_id))


@router.put("/chunks/{chunk_id}/translation", response_model=ChunkRead)
def put_chunk_translation(
    chunk_id: str, payload: TranslationUpdate, session: Session = Depends(db_session)
) -> ChunkRead:
    upsert_translation(session, chunk_id, payload)
    from jlpt_studio.services.chunks import get_chunk_or_404
    return chunk_to_read(session, get_chunk_or_404(session, chunk_id))


@router.put("/chunks/{chunk_id}/furigana", response_model=ChunkRead)
def put_chunk_furigana(
    chunk_id: str, payload: FuriganaUpdate, session: Session = Depends(db_session)
) -> ChunkRead:
    upsert_furigana(session, chunk_id, payload)
    from jlpt_studio.services.chunks import get_chunk_or_404
    return chunk_to_read(session, get_chunk_or_404(session, chunk_id))


@router.post("/chunks/{chunk_id}/reprocess", response_model=JobRead, status_code=202)
def reprocess_chunk(
    chunk_id: str, payload: ReprocessRequest, session: Session = Depends(db_session)
) -> JobRead:
    from jlpt_studio.services.chunks import get_chunk_or_404

    chunk = get_chunk_or_404(session, chunk_id)
    job = enqueue_job(
        session,
        project_id=chunk.project_id,
        job_type="process_project",
        payload={"stages": payload.stages, "force": True, "segmentation_preset": "balanced", "chunk_ids": payload.chunk_ids},
    )
    return job_to_read(job)


@router.post("/chunks/{chunk_id}/transcribe", response_model=JobRead, status_code=202)
def transcribe_chunk(chunk_id: str, session: Session = Depends(db_session)) -> JobRead:
    return reprocess_chunk(chunk_id, ReprocessRequest(stages=["asr"], chunk_ids=[chunk_id]), session)


@router.post("/chunks/{chunk_id}/confirm", response_model=ChunkRead)
def confirm_chunk_reference(chunk_id: str, payload: ReferenceUpdate, session: Session = Depends(db_session)) -> ChunkRead:
    payload.confirm = True
    return put_chunk_reference(chunk_id, payload, session)


@router.post("/chunks/{chunk_id}/furigana", response_model=JobRead, status_code=202)
def generate_chunk_furigana(chunk_id: str, session: Session = Depends(db_session)) -> JobRead:
    from jlpt_studio.services.chunks import get_chunk_or_404
    chunk = get_chunk_or_404(session, chunk_id)
    job = enqueue_job(session, project_id=chunk.project_id, job_type="process_project", payload={"stages": ["furigana"], "force": True, "chunk_ids": [chunk_id], "segmentation_preset": "balanced"})
    return job_to_read(job)


@router.post("/chunks/{chunk_id}/translate", response_model=JobRead, status_code=202)
def translate_chunk(chunk_id: str, session: Session = Depends(db_session)) -> JobRead:
    from jlpt_studio.services.chunks import get_chunk_or_404
    chunk = get_chunk_or_404(session, chunk_id)
    job = enqueue_job(session, project_id=chunk.project_id, job_type="process_project", payload={"stages": ["translation"], "force": True, "chunk_ids": [chunk_id], "segmentation_preset": "balanced"})
    return job_to_read(job)


@router.post("/projects/{project_id}/translate-batch")
def translate_batch(project_id: str, payload: TranslateBatchRequest, session: Session = Depends(db_session), settings: Settings = Depends(runtime_settings)) -> dict[str, int]:
    get_project_or_404(session, project_id)
    count = translate_project_chunks(session, settings, project_id, batch_size=payload.batch_size, context_size=payload.context_size, chunk_ids=set(payload.chunk_ids) if payload.chunk_ids else None)
    return {"translated_count": count}


@router.post(
    "/projects/{project_id}/exercises/generate", response_model=list[ExerciseRead], status_code=201
)
def post_exercises(
    project_id: str,
    payload: CreateExercisesRequest,
    session: Session = Depends(db_session),
) -> list[ExerciseRead]:
    return generate_exercises(
        session,
        project_id,
        mode=payload.mode,
        chunk_ids=payload.chunk_ids,
        settings=payload.settings,
    )


@router.get("/projects/{project_id}/practice-session", response_model=list[ExerciseRead])
def get_practice_session(
    project_id: str,
    mode: str | None = None,
    session: Session = Depends(db_session),
) -> list[ExerciseRead]:
    return list_exercises(session, project_id, mode)


@router.get("/exercises/{exercise_id}/answer", response_model=ExerciseAnswerRead)
def get_exercise_answer(exercise_id: str, session: Session = Depends(db_session)) -> ExerciseAnswerRead:
    return exercise_answer(session, exercise_id)


@router.patch("/exercises/{exercise_id}", response_model=ExerciseRead)
def patch_exercise(
    exercise_id: str,
    payload: ExerciseUpdate,
    session: Session = Depends(db_session),
) -> ExerciseRead:
    return _exercise_to_read(session, update_exercise(session, exercise_id, payload))


@router.post("/exercises/{exercise_id}/attempts", response_model=AttemptRead, status_code=201)
def post_attempt(
    exercise_id: str,
    payload: AttemptCreate,
    session: Session = Depends(db_session),
) -> AttemptRead:
    return submit_attempt(session, exercise_id, payload)


@router.get("/projects/{project_id}/segmentation-metrics", response_model=SegmentationMetricsRead)
def get_segmentation_metrics(project_id: str, session: Session = Depends(db_session)) -> SegmentationMetricsRead:
    return segmentation_metrics(session, project_id)


@router.post("/projects/{project_id}/export")
def post_export(project_id: str, payload: ExportRequest, session: Session = Depends(db_session), settings: Settings = Depends(runtime_settings)) -> dict[str, object]:
    path = export_project(session, settings, project_id, payload)
    return {"path": str(path), "filename": path.name, "download_url": f"/api/projects/{project_id}/export/download"}


@router.get("/projects/{project_id}/export/download")
def download_export(project_id: str, session: Session = Depends(db_session), settings: Settings = Depends(runtime_settings)) -> FileResponse:
    get_project_or_404(session, project_id)
    root = project_dir(settings, project_id) / "exports"
    candidates = sorted(root.glob("jlpt-studio-*"), key=lambda item: item.stat().st_mtime, reverse=True) if root.exists() else []
    if not candidates:
        raise NotFoundError("Chưa có file export. Hãy export project trước.")
    path = candidates[0]
    return FileResponse(path, filename=path.name, media_type="application/zip" if path.suffix == ".zip" else "application/json")


@router.post("/projects/{project_id}/cleanup", response_model=CleanupRead)
def post_cleanup(project_id: str, session: Session = Depends(db_session), settings: Settings = Depends(runtime_settings)) -> CleanupRead:
    return cleanup_project(session, settings, project_id)


@router.get("/projects/{project_id}/stats")
def get_project_stats(
    project_id: str, session: Session = Depends(db_session)
) -> dict[str, float | int]:
    return project_stats(session, project_id)
