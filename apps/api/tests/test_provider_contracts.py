from __future__ import annotations

from jlpt_studio.pipeline.chunker import semantic_chunk
from jlpt_studio.pipeline.types import ChunkCandidate, SegmentationConfig
from jlpt_studio.providers.llm.llama_cpp import GemmaTranslator


def test_gemma_parser_accepts_fenced_json_and_exact_ids() -> None:
    parsed = GemmaTranslator._parse('```json\n{"translations":[{"chunk_id":"a","translation_vi":"Xin chào"}]}\n```', {"a"})
    assert parsed == {"a": "Xin chào"}


def test_semantic_chunk_never_exceeds_audio8_cap() -> None:
    items = [ChunkCandidate(0, 65_000, "SPEAKER_00")]
    chunks = semantic_chunk(items, SegmentationConfig(hard_asr_cap_ms=28_000))
    assert chunks
    assert max(item.duration_ms for item in chunks) <= 28_000
