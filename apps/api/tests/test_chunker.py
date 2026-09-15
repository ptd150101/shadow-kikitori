from jlpt_studio.pipeline.chunker import intersect_vad_and_diarization, semantic_chunk
from jlpt_studio.pipeline.types import SegmentationConfig, SpeakerTurn, SpeechRegion


def test_chunker_merges_close_same_speaker_regions() -> None:
    regions = [SpeechRegion(0, 900), SpeechRegion(1200, 2200), SpeechRegion(2450, 3500)]
    turns = [SpeakerTurn(0, 4000, "SPEAKER_00")]
    chunks = semantic_chunk(intersect_vad_and_diarization(regions, turns), SegmentationConfig())
    assert len(chunks) == 1
    assert chunks[0].start_ms == 0
    assert chunks[0].end_ms == 3500


def test_chunker_respects_speaker_change() -> None:
    regions = [SpeechRegion(0, 1800), SpeechRegion(1900, 3600)]
    turns = [SpeakerTurn(0, 1850, "SPEAKER_00"), SpeakerTurn(1850, 4000, "SPEAKER_01")]
    chunks = semantic_chunk(intersect_vad_and_diarization(regions, turns), SegmentationConfig())
    assert [chunk.speaker_label for chunk in chunks] == ["SPEAKER_00", "SPEAKER_01"]


def test_chunker_keeps_under_audio8_cap() -> None:
    regions = [SpeechRegion(start, start + 1000) for start in range(0, 30000, 1200)]
    turns = [SpeakerTurn(0, 40000, "SPEAKER_00")]
    chunks = semantic_chunk(intersect_vad_and_diarization(regions, turns), SegmentationConfig())
    assert chunks
    assert all(chunk.duration_ms <= 28000 for chunk in chunks)

