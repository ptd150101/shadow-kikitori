from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import MediaAsset
from jlpt_studio.media.ffmpeg import FfmpegRunner
from jlpt_studio.services.paths import project_asset_dir, resolve_relative_project_path


def analysis_asset_for_project(session: Session, project_id: str) -> MediaAsset:
    asset = (
        session.query(MediaAsset).filter_by(project_id=project_id, kind="analysis").one_or_none()
    )
    if asset is None:
        raise NotFoundError("Project chưa có audio analysis. Hãy chạy normalize trước.")
    return asset


def cached_chunk_wav(
    session: Session,
    settings: Settings,
    ffmpeg: FfmpegRunner,
    *,
    project_id: str,
    start_ms: int,
    end_ms: int,
) -> Path:
    asset = analysis_asset_for_project(session, project_id)
    material = f"{asset.sha256}:{start_ms}:{end_ms}:pcm16-mono-16k-v1"
    key = hashlib.sha256(material.encode("utf-8")).hexdigest()
    target = project_asset_dir(settings, project_id, "chunk-cache") / f"{key}.wav"
    if not target.exists():
        ffmpeg.slice_wav(
            resolve_relative_project_path(settings, asset.relative_path), target, start_ms, end_ms
        )
    return target
