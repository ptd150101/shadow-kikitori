from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import AppSettingsRead, AppSettingsUpdate
from jlpt_studio.core.config import Settings
from jlpt_studio.db.models import AppSetting

RUNTIME_SETTINGS_KEY = "runtime-settings-v1"
ALLOWED_FIELDS = {
    "ffmpeg_path",
    "ffprobe_path",
    "ytdlp_path",
    "device",
    "llm_base_url",
    "llm_model",
    "audio8_model_id",
    "audio8_revision",
    "pyannote_model_path",
    "hf_token",
    "llm_mode",
    "llm_executable",
    "llm_model_path",
    "llm_port",
}


def get_runtime_settings(session: Session, base: Settings) -> Settings:
    stored = session.get(AppSetting, RUNTIME_SETTINGS_KEY)
    values = stored.value_json if stored else {}
    allowed_values = {key: value for key, value in values.items() if key in ALLOWED_FIELDS}
    for key in ("pyannote_model_path", "llm_executable", "llm_model_path"):
        if allowed_values.get(key):
            allowed_values[key] = Path(str(allowed_values[key])).expanduser()
    return base.model_copy(update=allowed_values)


def settings_to_read(settings: Settings) -> AppSettingsRead:
    return AppSettingsRead(
        ffmpeg_path=settings.ffmpeg_path,
        ffprobe_path=settings.ffprobe_path,
        ytdlp_path=settings.ytdlp_path,
        audio8_model_id=settings.audio8_model_id,
        audio8_revision=settings.audio8_revision,
        pyannote_model_path=str(settings.pyannote_model_path)
        if settings.pyannote_model_path
        else None,
        device=settings.device,
        llm_mode=settings.llm_mode,
        llm_base_url=settings.llm_base_url,
        llm_model=settings.llm_model,
        llm_executable=str(settings.llm_executable) if settings.llm_executable else None,
        llm_model_path=str(settings.llm_model_path) if settings.llm_model_path else None,
        audio8_max_seconds=settings.audio8_max_seconds,
    )


def update_runtime_settings(
    session: Session, base: Settings, payload: AppSettingsUpdate
) -> Settings:
    current = session.get(AppSetting, RUNTIME_SETTINGS_KEY)
    values = dict(current.value_json) if current else {}
    for key, value in payload.model_dump(exclude_none=True).items():
        if key in ALLOWED_FIELDS:
            if key in {"pyannote_model_path", "llm_executable", "llm_model_path"} and value:
                value = str(Path(value).expanduser())
            values[key] = value
    if current is None:
        current = AppSetting(key=RUNTIME_SETTINGS_KEY, value_json=values)
        session.add(current)
    else:
        current.value_json = values
    session.commit()
    normalized = dict(values)
    for key in ("pyannote_model_path", "llm_executable", "llm_model_path"):
        if normalized.get(key):
            normalized[key] = Path(str(normalized[key])).expanduser()
    return base.model_copy(update=normalized)
