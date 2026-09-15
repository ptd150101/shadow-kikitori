from __future__ import annotations

import json
import logging
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import StudioError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration_ms: int
    sample_rate: int | None
    channels: int | None
    codec_name: str | None
    format_name: str | None


class FfmpegRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def has_ffmpeg(self) -> bool:
        return shutil.which(self.settings.ffmpeg_path) is not None

    def has_ffprobe(self) -> bool:
        return shutil.which(self.settings.ffprobe_path) is not None

    def _run(
        self, args: Sequence[str], *, timeout: int = 60 * 30
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                list(args),
                check=True,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise StudioError(
                "TOOL_NOT_FOUND", f"Không tìm thấy công cụ: {args[0]}", status_code=503
            ) from error
        except subprocess.TimeoutExpired as error:
            raise StudioError(
                "MEDIA_TIMEOUT", "Xử lý media quá thời gian cho phép", status_code=504
            ) from error
        except subprocess.CalledProcessError as error:
            logger.warning("media command failed: %s", error.stderr[-1000:])
            raise StudioError(
                "MEDIA_PROCESS_FAILED",
                "FFmpeg không thể xử lý file audio này",
                {"stderr": error.stderr[-1000:]},
                422,
            ) from error

    def probe(self, source: Path) -> MediaInfo:
        result = self._run(
            [
                self.settings.ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration,format_name:stream=codec_type,codec_name,sample_rate,channels",
                "-of",
                "json",
                str(source),
            ],
            timeout=60,
        )
        try:
            data = json.loads(result.stdout)
            audio_stream = next(
                (
                    stream
                    for stream in data.get("streams", [])
                    if stream.get("codec_type") == "audio"
                ),
                None,
            )
            if not audio_stream:
                raise ValueError("no audio stream")
            duration = float(data.get("format", {}).get("duration", 0))
            return MediaInfo(
                duration_ms=max(0, round(duration * 1000)),
                sample_rate=int(audio_stream["sample_rate"])
                if audio_stream.get("sample_rate")
                else None,
                channels=int(audio_stream["channels"]) if audio_stream.get("channels") else None,
                codec_name=audio_stream.get("codec_name"),
                format_name=data.get("format", {}).get("format_name"),
            )
        except (ValueError, TypeError, KeyError) as error:
            raise StudioError(
                "INVALID_MEDIA", "File không chứa audio hợp lệ", status_code=422
            ) from error

    def normalize(
        self, source: Path, playback_target: Path, analysis_target: Path
    ) -> tuple[MediaInfo, MediaInfo]:
        playback_target.parent.mkdir(parents=True, exist_ok=True)
        analysis_target.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-c:a",
                "libopus",
                "-b:a",
                "96k",
                str(playback_target),
            ]
        )
        self._run(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(analysis_target),
            ]
        )
        return self.probe(playback_target), self.probe(analysis_target)

    def slice_wav(self, source: Path, target: Path, start_ms: int, end_ms: int) -> None:
        if end_ms <= start_ms:
            raise StudioError("INVALID_CHUNK_BOUNDARY", "Khoảng audio không hợp lệ")
        target.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                self.settings.ffmpeg_path,
                "-y",
                "-ss",
                f"{start_ms / 1000:.3f}",
                "-to",
                f"{end_ms / 1000:.3f}",
                "-i",
                str(source),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            timeout=120,
        )
