from __future__ import annotations

from pathlib import Path

from jlpt_studio.core.errors import ProviderUnavailableError, StudioError
from jlpt_studio.pipeline.types import SegmentationConfig, SpeechRegion


class SileroVadProvider:
    """Lazy Silero wrapper so normal API operations do not import torch."""

    def speech_regions(self, audio_path: Path, config: SegmentationConfig) -> list[SpeechRegion]:
        try:
            from silero_vad import get_speech_timestamps, load_silero_vad, read_audio
        except ImportError as error:
            raise ProviderUnavailableError(
                "silero-vad", "Chưa cài AI dependencies. Chạy `uv sync --group ai`."
            ) from error
        try:
            model = load_silero_vad()
            waveform = read_audio(str(audio_path), sampling_rate=16000)
            timestamps = get_speech_timestamps(
                waveform,
                model,
                sampling_rate=16000,
                threshold=config.vad_threshold,
                min_speech_duration_ms=config.min_speech_ms,
                min_silence_duration_ms=config.min_silence_ms,
                speech_pad_ms=config.speech_pad_ms,
                return_seconds=False,
            )
        except Exception as error:  # provider errors vary by torch/silero version
            raise StudioError(
                "VAD_FAILED", f"Silero VAD thất bại: {error}", status_code=422
            ) from error
        regions: list[SpeechRegion] = []
        for item in timestamps:
            start = round(int(item["start"]) / 16)
            end = round(int(item["end"]) / 16)
            if end > start:
                regions.append(SpeechRegion(start, end))
        return regions
