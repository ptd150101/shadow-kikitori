from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SpeechRegion:
    start_ms: int
    end_ms: int
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class SpeakerTurn:
    start_ms: int
    end_ms: int
    speaker_label: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class ChunkCandidate:
    start_ms: int
    end_ms: int
    speaker_label: str
    vad_confidence: float | None = None
    diarization_confidence: float | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


@dataclass(frozen=True, slots=True)
class SegmentationConfig:
    vad_threshold: float = 0.5
    min_speech_ms: int = 250
    min_silence_ms: int = 350
    speech_pad_ms: int = 150
    merge_gap_ms: int = 1200
    min_chunk_ms: int = 1200
    target_chunk_ms: int = 10_000
    max_chunk_ms: int = 18_000
    hard_asr_cap_ms: int = 28_000

    @classmethod
    def from_preset(cls, name: str) -> SegmentationConfig:
        if name == "fewer":
            return cls(merge_gap_ms=1600, target_chunk_ms=14_000, max_chunk_ms=24_000)
        if name == "short":
            return cls(merge_gap_ms=800, target_chunk_ms=7000, max_chunk_ms=12_000)
        return cls()
