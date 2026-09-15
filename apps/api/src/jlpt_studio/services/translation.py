from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import TranslationUpdate
from jlpt_studio.core.config import Settings
from jlpt_studio.core.errors import NotFoundError
from jlpt_studio.db.models import Chunk, ChunkText, Speaker, TranslationCache
from jlpt_studio.providers.llm import PROMPT_VERSION, GemmaTranslator


def upsert_translation(session: Session, chunk_id: str, payload: TranslationUpdate) -> ChunkText:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None:
        raise NotFoundError("Không tìm thấy audio chunk")
    text = session.get(ChunkText, chunk_id)
    if text is None:
        text = ChunkText(chunk_id=chunk_id)
        session.add(text)
    text.translation_vi = payload.translation_vi.strip()
    text.translation_status = "user_confirmed" if payload.confirm else "ai_unverified"
    text.translation_context_hash = None
    text.translation_input_hash = None
    session.commit()
    session.refresh(text)
    return text


def _context_digest(items: list[dict[str, str]]) -> str:
    material = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def translation_cache_key(
    settings: Settings,
    *,
    previous: list[dict[str, str]],
    targets: list[dict[str, str]],
    future: list[dict[str, str]],
) -> str:
    material = {
        "previous": previous,
        "targets": targets,
        "future": future,
        "target_language": "vi",
        "model": settings.llm_model,
        "prompt_version": PROMPT_VERSION,
        "temperature": 0.1,
    }
    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _chunk_item(session: Session, chunk: Chunk) -> dict[str, str] | None:
    text = session.get(ChunkText, chunk.id)
    content = (
        text.reference_text
        if text and text.reference_text
        else (text.asr_normalized if text else None)
    )
    if not content:
        return None
    speaker = session.get(Speaker, chunk.speaker_id) if chunk.speaker_id else None
    return {
        "chunk_id": chunk.id,
        "speaker": speaker.display_name if speaker else "Speaker",
        "text": content,
    }


def translate_project_chunks(
    session: Session,
    settings: Settings,
    project_id: str,
    *,
    batch_size: int = 10,
    context_size: int = 4,
    translator: GemmaTranslator | None = None,
    chunk_ids: set[str] | None = None,
) -> int:
    chunks = session.query(Chunk).filter_by(project_id=project_id).order_by(Chunk.order_index).all()
    if chunk_ids is not None:
        chunks = [chunk for chunk in chunks if chunk.id in chunk_ids]
    items = [(chunk, _chunk_item(session, chunk)) for chunk in chunks]
    valid = [(chunk, item) for chunk, item in items if item]
    if not valid:
        return 0
    translator = translator or GemmaTranslator(settings)
    translated_count = 0
    for start in range(0, len(valid), batch_size):
        target_pairs = valid[start : start + batch_size]
        previous = [item for _, item in valid[max(0, start - context_size) : start] if item]
        future = [
            item
            for _, item in valid[start + batch_size : start + batch_size + context_size]
            if item
        ]
        targets = [item for _, item in target_pairs if item]
        cache_key = translation_cache_key(
            settings, previous=previous, targets=targets, future=future
        )
        cached = session.get(TranslationCache, cache_key)
        if cached:
            translations = cached.translation_json["translations"]
        else:
            mapping = translator.translate_batch(
                previous_context=previous, targets=targets, future_context=future
            )
            translations = [
                {"chunk_id": chunk_id, "translation_vi": value}
                for chunk_id, value in mapping.items()
            ]
            session.add(
                TranslationCache(
                    key=cache_key,
                    translation_json={"translations": translations},
                    model_id=settings.llm_model,
                    prompt_version=PROMPT_VERSION,
                )
            )
        by_id = {item["chunk_id"]: item["translation_vi"] for item in translations}
        context_hash = _context_digest(previous + targets + future)
        for chunk, _ in target_pairs:
            text = session.get(ChunkText, chunk.id)
            if text is None or chunk.id not in by_id:
                continue
            if text.translation_status == "user_confirmed":
                continue
            text.translation_vi = by_id[chunk.id]
            text.translation_status = "ready"
            text.translation_context_hash = context_hash
            text.translation_input_hash = cache_key
            text.updated_at = datetime.now(UTC)
            translated_count += 1
        session.commit()
    return translated_count
