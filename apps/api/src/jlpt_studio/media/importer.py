from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import UploadFile
from sqlalchemy import delete
from sqlalchemy.orm import Session

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import StudioError
from jlpt_studio.db.models import Chunk, MediaAsset, PipelineArtifact, Project
from jlpt_studio.media.ffmpeg import FfmpegRunner, MediaInfo
from jlpt_studio.services.paths import project_asset_dir, to_relative_project_path

SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(slots=True)
class ImportedSource:
    path: Path
    original_name: str
    size_bytes: int
    sha256: str
    media_info: MediaInfo
    mime_type: str | None = None
    metadata: dict[str, object] | None = None


def _safe_name(name: str) -> str:
    stem = SAFE_FILENAME.sub("-", Path(name).stem).strip(".-") or "audio"
    suffix = SAFE_FILENAME.sub("", Path(name).suffix.lower())[:12]
    return f"{stem[:96]}{suffix}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class MediaImporter:
    def __init__(self, settings: Settings, ffmpeg: FfmpegRunner | None = None) -> None:
        self.settings = settings
        self.ffmpeg = ffmpeg or FfmpegRunner(settings)

    def import_upload(self, project: Project, upload: UploadFile) -> ImportedSource:
        name = _safe_name(upload.filename or "upload.audio")
        allowed_suffixes = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".webm", ".mov", ".mkv"}
        if Path(name).suffix.lower() not in allowed_suffixes:
            raise StudioError("UNSUPPORTED_MEDIA", "Định dạng media không được hỗ trợ", status_code=415)
        target_dir = project_asset_dir(self.settings, project.id, "source")
        target = target_dir / name
        counter = 1
        while target.exists():
            target = target_dir / f"{Path(name).stem}-{counter}{Path(name).suffix}"
            counter += 1
        size = 0
        try:
            with target.open("wb") as handle:
                while block := upload.file.read(1024 * 1024):
                    size += len(block)
                    if size > self.settings.max_upload_bytes:
                        raise StudioError(
                            "UPLOAD_TOO_LARGE",
                            "File vượt quá dung lượng tối đa cho phép",
                            status_code=413,
                        )
                    handle.write(block)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return self._inspect_source(target, upload.filename or name, size, upload.content_type)

    def import_youtube(self, project: Project, source_url: str) -> ImportedSource:
        parsed = urlparse(source_url)
        hostname = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or hostname not in {
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
        }:
            raise StudioError(
                "INVALID_YOUTUBE_URL", "Chỉ hỗ trợ URL YouTube hợp lệ", status_code=422
            )
        if "list" in parse_qs(parsed.query) or parsed.path.rstrip("/").endswith("/playlist"):
            raise StudioError("YOUTUBE_PLAYLIST_UNSUPPORTED", "Chỉ import một video YouTube, không hỗ trợ playlist", status_code=422)
        target_dir = project_asset_dir(self.settings, project.id, "source")
        template = str(target_dir / "youtube-source.%(ext)s")
        info_command = [
            self.settings.ytdlp_path,
            "--no-playlist",
            "--dump-single-json",
            "--skip-download",
            source_url,
        ]
        command = [
            self.settings.ytdlp_path,
            "--no-playlist",
            "--no-progress",
            "--restrict-filenames",
            "-f",
            "bestaudio/best",
            "-o",
            template,
            source_url,
        ]
        metadata: dict[str, object] = {}
        try:
            info_result = subprocess.run(info_command, check=True, capture_output=True, text=True, timeout=90)
            try:
                raw = json.loads(info_result.stdout)
                metadata = {key: raw.get(key) for key in ("id", "title", "thumbnail", "uploader", "upload_date", "webpage_url") if raw.get(key) is not None}
            except json.JSONDecodeError:
                metadata = {}
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=60 * 30)
        except FileNotFoundError as error:
            raise StudioError(
                "YTDLP_NOT_FOUND", "Không tìm thấy yt-dlp", status_code=503
            ) from error
        except subprocess.TimeoutExpired as error:
            raise StudioError(
                "YOUTUBE_TIMEOUT", "Tải audio YouTube quá thời gian", status_code=504
            ) from error
        except subprocess.CalledProcessError as error:
            stderr = error.stderr.lower()
            code = "YOUTUBE_DOWNLOAD_FAILED"
            if "private video" in stderr:
                code = "YOUTUBE_PRIVATE"
            elif "sign in" in stderr or "cookies" in stderr:
                code = "YOUTUBE_AUTH_REQUIRED"
            elif "unavailable" in stderr:
                code = "YOUTUBE_UNAVAILABLE"
            elif "update" in stderr or "outdated" in stderr:
                code = "YTDLP_OUTDATED"
            raise StudioError(
                code, "Không thể tải audio từ YouTube", {"stderr": error.stderr[-1200:]}, 422
            ) from error
        sources = sorted(
            target_dir.glob("youtube-source.*"), key=lambda path: path.stat().st_mtime, reverse=True
        )
        if not sources:
            raise StudioError(
                "YOUTUBE_DOWNLOAD_FAILED", "yt-dlp không tạo được file audio", status_code=422
            )
        target = sources[0]
        return self._inspect_source(target, target.name, target.stat().st_size, "audio/*", metadata)

    def _inspect_source(
        self,
        target: Path,
        original_name: str,
        size: int,
        mime_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ImportedSource:
        media_info = self.ffmpeg.probe(target)
        if media_info.duration_ms <= 0:
            target.unlink(missing_ok=True)
            raise StudioError("INVALID_MEDIA", "Audio không có thời lượng hợp lệ", status_code=422)
        if media_info.duration_ms > self.settings.max_duration_seconds * 1000:
            target.unlink(missing_ok=True)
            raise StudioError(
                "MEDIA_TOO_LONG", "Audio vượt thời lượng tối đa cho phép", status_code=413
            )
        return ImportedSource(target, original_name, size, _sha256(target), media_info, mime_type, metadata or {})

    def persist_source_asset(
        self, session: Session, project: Project, source: ImportedSource
    ) -> MediaAsset:
        # A new source invalidates all derived assets/artifacts/chunks atomically.
        project_root = self.settings.resolved_data_dir / "projects" / project.id
        for category in ("normalized", "waveform", "chunk-cache", "exports"):
            shutil.rmtree(project_root / category, ignore_errors=True)
        session.execute(delete(Chunk).where(Chunk.project_id == project.id))
        session.execute(delete(PipelineArtifact).where(PipelineArtifact.project_id == project.id))
        for kind in ("playback", "analysis", "waveform"):
            derived = session.query(MediaAsset).filter_by(project_id=project.id, kind=kind).all()
            for item in derived:
                session.delete(item)
        existing = (
            session.query(MediaAsset).filter_by(project_id=project.id, kind="source").one_or_none()
        )
        if existing:
            old_path = self.settings.resolved_data_dir / existing.relative_path
            session.delete(existing)
            session.flush()
            if old_path != source.path:
                old_path.unlink(missing_ok=True)
        asset = MediaAsset(
            project_id=project.id,
            kind="source",
            relative_path=to_relative_project_path(self.settings, source.path),
            original_name=source.original_name,
            mime_type=source.mime_type,
            size_bytes=source.size_bytes,
            duration_ms=source.media_info.duration_ms,
            sample_rate=source.media_info.sample_rate,
            channels=source.media_info.channels,
            sha256=source.sha256,
            metadata_json={
                "codec_name": source.media_info.codec_name,
                "format_name": source.media_info.format_name,
                **(source.metadata or {}),
            },
        )
        session.add(asset)
        project.status = "imported"
        session.commit()
        session.refresh(asset)
        return asset
