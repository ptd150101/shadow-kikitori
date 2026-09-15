from __future__ import annotations

import importlib.util
import shutil

from jlpt_studio.core.config import Settings
from jlpt_studio.media.ffmpeg import FfmpegRunner
from jlpt_studio.providers.llm import GemmaTranslator


def _module_ready(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError):
        return False


def provider_status(settings: Settings) -> list[dict[str, str | bool]]:
    """Cheap health checks used by Settings; never load a multi-GB model."""
    ffmpeg = FfmpegRunner(settings)
    audio8 = _module_ready("torch") and _module_ready("transformers")
    pyannote = _module_ready("pyannote.audio") and bool(
        (settings.pyannote_model_path and settings.pyannote_model_path.exists()) or settings.hf_token
    )
    llm_ready, llm_detail = GemmaTranslator(settings).health_check()
    return [
        {"name": "FFmpeg", "ready": ffmpeg.has_ffmpeg(), "detail": "Đã tìm thấy" if ffmpeg.has_ffmpeg() else "Thiếu ffmpeg trong PATH"},
        {"name": "FFprobe", "ready": ffmpeg.has_ffprobe(), "detail": "Đã tìm thấy" if ffmpeg.has_ffprobe() else "Thiếu ffprobe trong PATH"},
        {"name": "yt-dlp", "ready": shutil.which(settings.ytdlp_path) is not None, "detail": "Đã tìm thấy" if shutil.which(settings.ytdlp_path) else "Thiếu yt-dlp trong PATH"},
        {"name": "Audio8 ASR", "ready": audio8, "detail": "Dependencies sẵn sàng" if audio8 else "Cài uv sync --group ai"},
        {"name": "Community-1 diarization", "ready": pyannote, "detail": "Local model/dependencies sẵn sàng" if pyannote else "Cài pyannote.audio và cấu hình model/token"},
        {"name": "Gemma 4 translation", "ready": llm_ready, "detail": llm_detail},
    ]


def model_paths(settings: Settings) -> dict[str, str | None]:
    return {
        "audio8_model_id": settings.audio8_model_id,
        "audio8_revision": settings.audio8_revision,
        "pyannote_model_path": str(settings.pyannote_model_path) if settings.pyannote_model_path else None,
        "llm_model": settings.llm_model,
        "llm_model_path": str(settings.llm_model_path) if settings.llm_model_path else None,
    }
