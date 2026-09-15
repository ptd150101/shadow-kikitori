from __future__ import annotations

from pathlib import Path

from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import ProviderUnavailableError, StudioError
from jlpt_studio.pipeline.types import SpeakerTurn


class CommunityDiarizationProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _device(self) -> str:
        if self.settings.device != "auto":
            return self.settings.device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def diarize(self, audio_path: Path, *, num_speakers: int | None = None) -> list[SpeakerTurn]:
        try:
            import torch
            from pyannote.audio import Pipeline
        except ImportError as error:
            raise ProviderUnavailableError(
                "pyannote-community-1", "Chưa cài pyannote.audio. Chạy `uv sync --group ai`."
            ) from error
        model_ref = (
            str(self.settings.pyannote_model_path)
            if self.settings.pyannote_model_path
            else "pyannote/speaker-diarization-community-1"
        )
        try:
            kwargs = (
                {"token": self.settings.hf_token} if not self.settings.pyannote_model_path else {}
            )
            pipeline = Pipeline.from_pretrained(model_ref, **kwargs)
            device = self._device()
            if device.startswith("cuda"):
                pipeline.to(torch.device(device))
            call_kwargs: dict[str, int] = {}
            if num_speakers:
                call_kwargs["num_speakers"] = num_speakers
            output = pipeline(str(audio_path), **call_kwargs)
            annotation = (
                getattr(output, "exclusive_speaker_diarization", None) or output.speaker_diarization
            )
            turns = [
                SpeakerTurn(
                    start_ms=round(turn.start * 1000),
                    end_ms=round(turn.end * 1000),
                    speaker_label=str(label),
                )
                for turn, _, label in annotation.itertracks(yield_label=True)
                if turn.end > turn.start
            ]
            return sorted(turns, key=lambda item: (item.start_ms, item.end_ms))
        except StudioError:
            raise
        except Exception as error:
            message = str(error)
            if "gated" in message.lower() or "token" in message.lower():
                raise StudioError(
                    "PYANNOTE_ACCESS_REQUIRED",
                    "Cần chấp nhận điều kiện Community-1 và cấu hình Hugging Face token cho lần tải đầu.",
                    status_code=503,
                ) from error
            raise StudioError(
                "DIARIZATION_FAILED", f"Speaker diarization thất bại: {message}", status_code=422
            ) from error
        finally:
            try:
                del pipeline  # type: ignore[possibly-undefined]
                if torch.cuda.is_available():  # type: ignore[possibly-undefined]
                    torch.cuda.empty_cache()  # type: ignore[possibly-undefined]
            except Exception:
                pass
