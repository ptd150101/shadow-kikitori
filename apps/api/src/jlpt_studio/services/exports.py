from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import CleanupRead, ExportRequest
from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import Attempt, Chunk, ChunkText, Exercise, MediaAsset, Project, Speaker
from jlpt_studio.services.paths import project_dir, resolve_relative_project_path


def project_payload(session: Session, project_id: str, include_attempts: bool = True) -> dict[str, object]:
    project = session.get(Project, project_id)
    if project is None:
        raise NotFoundError("Không tìm thấy project")
    chunks = session.scalars(select(Chunk).where(Chunk.project_id == project_id).order_by(Chunk.order_index)).all()
    speakers = session.scalars(select(Speaker).where(Speaker.project_id == project_id)).all()
    exercises = session.scalars(select(Exercise).where(Exercise.project_id == project_id)).all()
    payload: dict[str, object] = {
        "schema_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "project": {"id": project.id, "title": project.title, "source_type": project.source_type, "source_url": project.source_url, "active_revision": project.active_revision, "language": project.language},
        "speakers": [{"id": item.id, "label": item.label, "display_name": item.display_name, "color": item.color} for item in speakers],
        "chunks": [],
        "exercises": [],
    }
    chunk_items = payload["chunks"]
    assert isinstance(chunk_items, list)
    for chunk in chunks:
        text = session.get(ChunkText, chunk.id)
        chunk_items.append({"id": chunk.id, "order_index": chunk.order_index, "start_ms": chunk.start_ms, "end_ms": chunk.end_ms, "speaker_id": chunk.speaker_id, "source": chunk.source, "text": {"asr_raw": text.asr_raw, "asr_normalized": text.asr_normalized, "reference_text": text.reference_text, "reference_status": text.reference_status, "furigana": text.furigana_json, "translation_vi": text.translation_vi} if text else None})
    exercise_items = payload["exercises"]
    assert isinstance(exercise_items, list)
    for exercise in exercises:
        item: dict[str, object] = {"id": exercise.id, "chunk_id": exercise.chunk_id, "mode": exercise.mode, "blank_spec": exercise.blank_spec_json, "settings": exercise.settings_json, "reference_revision": exercise.reference_revision, "status": exercise.status, "is_difficult": exercise.is_difficult}
        if include_attempts:
            item["attempts"] = [{"id": attempt.id, "answer_text": attempt.answer_text, "score": attempt.score, "strict_score": attempt.strict_score, "diff": attempt.diff_json, "revealed_answer": attempt.revealed_answer, "duration_ms": attempt.duration_ms, "created_at": attempt.created_at.isoformat()} for attempt in session.scalars(select(Attempt).where(Attempt.exercise_id == exercise.id).order_by(Attempt.created_at)).all()]
        exercise_items.append(item)
    return payload


def export_project(session: Session, settings: Settings, project_id: str, payload: ExportRequest) -> Path:
    data = project_payload(session, project_id, payload.include_attempts)
    target = project_dir(settings, project_id) / "exports" / f"jlpt-studio-{project_id[:8]}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    if payload.include_audio:
        asset = session.scalar(select(MediaAsset).where(MediaAsset.project_id == project_id, MediaAsset.kind == "playback"))
        if asset:
            archive = target.with_suffix(".zip")
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.write(target, target.name)
                path = resolve_relative_project_path(settings, asset.relative_path)
                if path.exists():
                    zf.write(path, f"audio/{path.name}")
            return archive
    return target


def cleanup_project(session: Session, settings: Settings, project_id: str) -> CleanupRead:
    if session.get(Project, project_id) is None:
        raise NotFoundError("Không tìm thấy project")
    root = project_dir(settings, project_id)
    removed_files = removed_bytes = removed_cache_files = 0
    cache = root / "chunk-cache"
    if cache.exists():
        for path in cache.glob("*.wav"):
            try:
                removed_bytes += path.stat().st_size
                path.unlink()
                removed_files += 1
                removed_cache_files += 1
            except OSError:
                continue
    return CleanupRead(removed_files=removed_files, removed_bytes=removed_bytes, removed_cache_files=removed_cache_files)
