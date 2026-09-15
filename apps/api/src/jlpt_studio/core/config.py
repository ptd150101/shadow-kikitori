from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from platformdirs import user_data_dir
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_prefix="JLPT_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "JLPT Listening Studio"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8765
    data_dir: Path | None = None
    database_url: str | None = None

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    ytdlp_path: str = "yt-dlp"
    max_upload_bytes: int = 2 * 1024 * 1024 * 1024
    max_duration_seconds: int = 2 * 60 * 60
    audio8_max_seconds: int = 28
    chunk_cache_retention_days: int = 30

    audio8_model_id: str = "Edge0/Audio8-ASR-0.1B"
    audio8_revision: str | None = None
    pyannote_model_path: Path | None = None
    hf_token: str | None = Field(default=None, repr=False)
    device: str = "auto"

    llm_mode: str = "external"  # external | managed
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL"
    llm_executable: Path | None = None
    llm_model_path: Path | None = None
    llm_port: int = 8080

    worker_poll_seconds: float = 0.5
    stale_job_seconds: int = 45

    @field_validator("llm_mode")
    @classmethod
    def validate_llm_mode(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in {"external", "managed"}:
            raise ValueError("llm_mode must be 'external' or 'managed'")
        return value

    @property
    def resolved_data_dir(self) -> Path:
        if self.data_dir:
            return self.data_dir.expanduser().resolve()
        return Path(user_data_dir("JLPTListeningStudio", "JLPTListeningStudio")).resolve()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.resolved_data_dir / 'studio.sqlite3'}"

    def ensure_directories(self) -> None:
        for path in (
            self.resolved_data_dir,
            self.resolved_data_dir / "projects",
            self.resolved_data_dir / "tmp",
            self.resolved_data_dir / "logs",
            self.resolved_data_dir / "models",
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
