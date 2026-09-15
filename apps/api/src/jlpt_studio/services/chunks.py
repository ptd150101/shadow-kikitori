from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import (
    ChunkRead,
    ChunkTextRead,
    ChunkUpdate,
    FuriganaUpdate,
    SpeakerRead,
    SpeakerUpdate,
    TimelineSnapshotRead,
)
from jlpt_studio.core.errors import ConflictError, NotFoundError, StudioError
from jlpt_studio.db.models import Chunk, ChunkText, Exercise, MediaAsset, Speaker
from jlpt_studio.services.projects import get_project_or_404


def _speaker_read(speaker: Speaker | None) -> SpeakerRead | None:
    if speaker is None:
        return None
    return SpeakerRead(
        id=speaker.id,
        label=speaker.label,
        display_name=speaker.display_name,
        color=speaker.color,
        is_manual=speaker.is_manual,
    )


def _text_read(text: ChunkText | None) -> ChunkTextRead | None:
    if text is None:
        return None
    return ChunkTextRead(
        asr_raw=text.asr_raw,
        asr_normalized=text.asr_normalized,
        reference_text=text.reference_text,
        reference_status=text.reference_status,
        furigana=text.furigana_json,
        furigana_status=text.furigana_status,
        translation_vi=text.translation_vi,
        translation_status=text.translation_status,
    )


def chunk_to_read(session: Session, chunk: Chunk, *, include_text: bool = True) -> ChunkRead:
    speaker = session.get(Speaker, chunk.speaker_id) if chunk.speaker_id else None
    text = session.get(ChunkText, chunk.id) if include_text else None
    return ChunkRead(
        id=chunk.id,
        project_id=chunk.project_id,
        speaker_id=chunk.speaker_id,
        order_index=chunk.order_index,
        start_ms=chunk.start_ms,
        end_ms=chunk.end_ms,
        source=chunk.source,
        status=chunk.status,
        boundary_revision=chunk.boundary_revision,
        speaker=_speaker_read(speaker),
        text=_text_read(text),
    )


def list_chunks(session: Session, project_id: str) -> list[ChunkRead]:
    get_project_or_404(session, project_id)
    chunks = session.scalars(
        select(Chunk).where(Chunk.project_id == project_id).order_by(Chunk.order_index.asc())
    ).all()
    return [chunk_to_read(session, chunk) for chunk in chunks]


def list_practice_chunks(session: Session, project_id: str) -> list[ChunkRead]:
    """Metadata-only chunks for practice mode (transcript never crosses this boundary)."""
    get_project_or_404(session, project_id)
    chunks = session.scalars(
        select(Chunk).where(Chunk.project_id == project_id).order_by(Chunk.order_index.asc())
    ).all()
    return [chunk_to_read(session, chunk, include_text=False) for chunk in chunks]


def get_chunk_or_404(session: Session, chunk_id: str) -> Chunk:
    chunk = session.get(Chunk, chunk_id)
    if chunk is None:
        raise NotFoundError("Không tìm thấy audio chunk")
    return chunk


def _assert_non_overlapping(session: Session, candidate: Chunk, start_ms: int, end_ms: int) -> None:
    overlap = session.scalar(
        select(Chunk.id).where(
            Chunk.project_id == candidate.project_id,
            Chunk.id != candidate.id,
            Chunk.start_ms < end_ms,
            Chunk.end_ms > start_ms,
        )
    )
    if overlap:
        raise ConflictError(
            "CHUNK_OVERLAP",
            "Biên chunk mới chồng lên một chunk khác. Hãy split hoặc merge trước.",
            {"overlapping_chunk_id": overlap},
        )


def invalidate_chunk_downstream(
    session: Session, chunk: Chunk, *, preserve_confirmed: bool = True
) -> None:
    text = session.get(ChunkText, chunk.id)
    if text:
        if not preserve_confirmed or text.reference_status != "user_confirmed":
            text.reference_status = "stale"
        text.furigana_status = "stale"
        text.translation_status = "stale"
        text.furigana_input_hash = None
        text.translation_input_hash = None
        text.translation_context_hash = None
    session.execute(delete(Exercise).where(Exercise.chunk_id == chunk.id))


def update_chunk(session: Session, chunk_id: str, payload: ChunkUpdate) -> Chunk:
    chunk = get_chunk_or_404(session, chunk_id)
    if (
        payload.expected_boundary_revision is not None
        and payload.expected_boundary_revision != chunk.boundary_revision
    ):
        raise ConflictError(
            "BOUNDARY_CONFLICT", "Chunk đã được chỉnh sửa ở phiên khác. Hãy tải lại timeline."
        )
    start_ms = payload.start_ms if payload.start_ms is not None else chunk.start_ms
    end_ms = payload.end_ms if payload.end_ms is not None else chunk.end_ms
    project = get_project_or_404(session, chunk.project_id)
    duration_ms = _project_duration_ms(session, project.id)
    if duration_ms is not None and end_ms > duration_ms:
        raise StudioError("CHUNK_OUT_OF_RANGE", "Chunk vượt quá thời lượng audio")
    if end_ms <= start_ms:
        raise StudioError("INVALID_CHUNK_BOUNDARY", "Điểm kết thúc phải lớn hơn điểm bắt đầu")
    if end_ms - start_ms > 28_000:
        raise StudioError("CHUNK_ASR_LIMIT_EXCEEDED", "Mỗi chunk phải ngắn hơn hoặc bằng 28 giây cho Audio8")
    boundary_changed = start_ms != chunk.start_ms or end_ms != chunk.end_ms
    if boundary_changed:
        _assert_non_overlapping(session, chunk, start_ms, end_ms)
        chunk.start_ms = start_ms
        chunk.end_ms = end_ms
        chunk.boundary_revision += 1
        invalidate_chunk_downstream(session, chunk)
    if "speaker_id" in payload.model_fields_set:
        if payload.speaker_id:
            speaker = session.get(Speaker, payload.speaker_id)
            if not speaker or speaker.project_id != chunk.project_id:
                raise StudioError("INVALID_SPEAKER", "Speaker không thuộc project này")
        chunk.speaker_id = payload.speaker_id
        text = session.get(ChunkText, chunk.id)
        if text:
            text.translation_status = "stale"
    if payload.status is not None:
        chunk.status = payload.status
    changed = boundary_changed or "speaker_id" in payload.model_fields_set or payload.status is not None
    if not changed:
        return chunk
    project.active_revision += 1
    session.commit()
    session.refresh(chunk)
    return chunk


def split_chunk(
    session: Session, chunk_id: str, at_ms: int, expected_revision: int | None = None
) -> tuple[Chunk, Chunk]:
    original = get_chunk_or_404(session, chunk_id)
    if expected_revision is not None and expected_revision != original.boundary_revision:
        raise ConflictError("BOUNDARY_CONFLICT", "Chunk đã được chỉnh sửa ở phiên khác")
    if at_ms <= original.start_ms + 250 or at_ms >= original.end_ms - 250:
        raise StudioError("INVALID_SPLIT_POINT", "Điểm tách phải cách mỗi biên ít nhất 250 ms")
    original_end_ms = original.end_ms
    later_chunks = session.scalars(
        select(Chunk)
        .where(Chunk.project_id == original.project_id, Chunk.order_index > original.order_index)
        .order_by(Chunk.order_index.desc())
    ).all()
    for chunk in later_chunks:
        chunk.order_index += 1
    left_end = at_ms
    right_start = at_ms
    original.end_ms = left_end
    original.boundary_revision += 1
    original.source = "manual"
    invalidate_chunk_downstream(session, original)
    right = Chunk(
        project_id=original.project_id,
        speaker_id=original.speaker_id,
        order_index=original.order_index + 1,
        start_ms=right_start,
        end_ms=original_end_ms,
        source="manual",
        status="draft",
        boundary_revision=1,
    )
    session.add(right)
    session.flush()
    session.add(ChunkText(chunk_id=right.id, reference_status="missing"))
    project = get_project_or_404(session, original.project_id)
    project.active_revision += 1
    session.commit()
    session.refresh(original)
    session.refresh(right)
    return original, right


def merge_chunks(
    session: Session, chunk_ids: Iterable[str], expected_project_revision: int | None = None
) -> Chunk:
    requested_ids = list(dict.fromkeys(chunk_ids))
    if len(requested_ids) < 2:
        raise StudioError("MERGE_NEEDS_TWO_CHUNKS", "Cần chọn ít nhất hai chunk để gộp")
    chunks = session.scalars(select(Chunk).where(Chunk.id.in_(requested_ids))).all()
    if len(chunks) != len(requested_ids):
        raise NotFoundError("Một hoặc nhiều chunk không tồn tại")
    project_ids = {chunk.project_id for chunk in chunks}
    if len(project_ids) != 1:
        raise StudioError("CROSS_PROJECT_MERGE", "Chỉ có thể gộp chunk trong cùng một project")
    project_id = next(iter(project_ids))
    project = get_project_or_404(session, project_id)
    if (
        expected_project_revision is not None
        and project.active_revision != expected_project_revision
    ):
        raise ConflictError(
            "PROJECT_REVISION_CONFLICT", "Timeline đã thay đổi. Hãy tải lại trước khi gộp."
        )
    chunks.sort(key=lambda item: item.order_index)
    expected_orders = list(range(chunks[0].order_index, chunks[0].order_index + len(chunks)))
    if [chunk.order_index for chunk in chunks] != expected_orders:
        raise StudioError("NON_CONTIGUOUS_MERGE", "Chỉ có thể gộp các chunk liền kề")
    primary = chunks[0]
    if chunks[-1].end_ms - primary.start_ms > 28_000:
        raise StudioError("CHUNK_ASR_LIMIT_EXCEEDED", "Chunk sau khi gộp vượt giới hạn 28 giây của Audio8")
    primary.end_ms = chunks[-1].end_ms
    primary.source = "manual"
    primary.boundary_revision += 1
    invalidate_chunk_downstream(session, primary, preserve_confirmed=False)
    for chunk in chunks[1:]:
        session.delete(chunk)
    later_chunks = session.scalars(
        select(Chunk)
        .where(Chunk.project_id == project_id, Chunk.order_index > chunks[-1].order_index)
        .order_by(Chunk.order_index.asc())
    ).all()
    reduction = len(chunks) - 1
    for chunk in later_chunks:
        chunk.order_index -= reduction
    project.active_revision += 1
    session.commit()
    session.refresh(primary)
    return primary


def upsert_reference(
    session: Session, chunk_id: str, reference_text: str, confirm: bool = True
) -> ChunkText:
    chunk = get_chunk_or_404(session, chunk_id)
    text = session.get(ChunkText, chunk.id)
    if text is None:
        text = ChunkText(chunk_id=chunk.id)
        session.add(text)
    text.reference_text = reference_text.strip()
    text.reference_status = "user_confirmed" if confirm else "ai_unverified"
    text.edited_at = datetime.now(UTC)
    text.confirmed_at = datetime.now(UTC) if confirm else None
    text.furigana_status = "stale"
    text.translation_status = "stale"
    session.execute(delete(Exercise).where(Exercise.chunk_id == chunk.id))
    project = get_project_or_404(session, chunk.project_id)
    project.active_revision += 1
    session.commit()
    session.refresh(text)
    return text


def upsert_furigana(session: Session, chunk_id: str, payload: FuriganaUpdate) -> ChunkText:
    chunk = get_chunk_or_404(session, chunk_id)
    text = session.get(ChunkText, chunk.id)
    if text is None:
        text = ChunkText(chunk_id=chunk.id)
        session.add(text)
    if text.reference_text and "".join(str(item.surface) for item in payload.furigana) != text.reference_text:
        raise StudioError("FURIGANA_TEXT_MISMATCH", "Furigana phải giữ nguyên chuỗi surface của transcript")
    text.furigana_json = [item.model_dump() for item in payload.furigana]
    text.furigana_status = "user_confirmed" if payload.confirm else "ready"
    text.furigana_input_hash = None
    session.commit()
    session.refresh(text)
    return text


def _project_duration_ms(session: Session, project_id: str) -> int | None:
    return session.scalar(
        select(MediaAsset.duration_ms).where(
            MediaAsset.project_id == project_id, MediaAsset.kind == "playback"
        )
    )


def list_speakers(session: Session, project_id: str) -> list[SpeakerRead]:
    get_project_or_404(session, project_id)
    speakers = session.scalars(
        select(Speaker).where(Speaker.project_id == project_id).order_by(Speaker.label)
    ).all()
    return [_speaker_read(item) for item in speakers if item is not None]


def create_speaker(
    session: Session, project_id: str, label: str, display_name: str | None, color: str
) -> Speaker:
    get_project_or_404(session, project_id)
    label = label.strip()
    if session.scalar(select(Speaker).where(Speaker.project_id == project_id, Speaker.label == label)):
        raise ConflictError("DUPLICATE_SPEAKER", "Speaker label đã tồn tại")
    speaker = Speaker(
        project_id=project_id,
        label=label,
        display_name=(display_name or label.replace("SPEAKER_", "Speaker ")).strip(),
        color=color,
        is_manual=True,
    )
    session.add(speaker)
    session.commit()
    session.refresh(speaker)
    return speaker


def update_speaker(session: Session, speaker_id: str, payload: SpeakerUpdate) -> Speaker:
    speaker = session.get(Speaker, speaker_id)
    if speaker is None:
        raise NotFoundError("Không tìm thấy speaker")
    if payload.display_name is not None:
        speaker.display_name = payload.display_name.strip()
    if payload.color is not None:
        speaker.color = payload.color
    speaker.is_manual = True
    session.commit()
    session.refresh(speaker)
    return speaker


def reorder_chunks(
    session: Session,
    project_id: str,
    ordered_chunk_ids: list[str],
    expected_project_revision: int | None = None,
) -> list[Chunk]:
    project = get_project_or_404(session, project_id)
    if expected_project_revision is not None and expected_project_revision != project.active_revision:
        raise ConflictError("PROJECT_REVISION_CONFLICT", "Timeline đã thay đổi. Hãy tải lại trước khi sắp xếp.")
    chunks = session.scalars(select(Chunk).where(Chunk.project_id == project_id)).all()
    by_id = {item.id: item for item in chunks}
    if set(by_id) != set(ordered_chunk_ids) or len(ordered_chunk_ids) != len(chunks):
        raise StudioError("INVALID_CHUNK_ORDER", "Danh sách chunk phải chứa đủ mỗi chunk đúng một lần")
    # Two-phase indexes avoid the unique(project_id, order_index) constraint in SQLite.
    for index, chunk in enumerate(chunks):
        chunk.order_index = -(index + 1)
    session.flush()
    for index, chunk_id in enumerate(ordered_chunk_ids):
        by_id[chunk_id].order_index = index
        by_id[chunk_id].source = "manual"
    project.active_revision += 1
    session.commit()
    return list(sorted(by_id.values(), key=lambda item: item.order_index))


def delete_chunk(
    session: Session, chunk_id: str, expected_project_revision: int | None = None
) -> None:
    chunk = get_chunk_or_404(session, chunk_id)
    project = get_project_or_404(session, chunk.project_id)
    if expected_project_revision is not None and expected_project_revision != project.active_revision:
        raise ConflictError("PROJECT_REVISION_CONFLICT", "Timeline đã thay đổi. Hãy tải lại trước khi xóa.")
    deleted_order = chunk.order_index
    session.delete(chunk)
    session.flush()
    later = session.scalars(
        select(Chunk).where(Chunk.project_id == project.id, Chunk.order_index > deleted_order)
    ).all()
    for item in later:
        item.order_index -= 1
    project.active_revision += 1
    session.commit()


def timeline_snapshot(session: Session, project_id: str) -> TimelineSnapshotRead:
    project = get_project_or_404(session, project_id)
    duration = _project_duration_ms(session, project_id)
    return TimelineSnapshotRead(
        project_id=project_id,
        revision=project.active_revision,
        duration_ms=duration,
        chunks=list_chunks(session, project_id),
    )


def replace_project_chunks(
    session: Session,
    project_id: str,
    items: list[dict[str, int | str | float | None]],
    speaker_ids_by_label: dict[str, str],
    preserve_manual: bool = True,
) -> list[Chunk]:
    """Replace auto chunks after segmentation while preserving manual edits only when not forced.

    This is intentionally a transaction-level operation: partial chunk lists are never visible.
    """
    project = get_project_or_404(session, project_id)
    existing_chunks = session.scalars(select(Chunk).where(Chunk.project_id == project_id)).all()
    if preserve_manual and any(chunk.source == "manual" for chunk in existing_chunks):
        return existing_chunks
    duration_ms = _project_duration_ms(session, project_id)
    validated: list[tuple[int, int]] = []
    previous_end = -1
    for item in items:
        start_ms, end_ms = int(item["start_ms"]), int(item["end_ms"])
        if start_ms < 0 or end_ms <= start_ms:
            raise StudioError("INVALID_CHUNK_BOUNDARY", "Biên chunk không hợp lệ")
        if duration_ms is not None and end_ms > duration_ms:
            raise StudioError("CHUNK_OUT_OF_RANGE", "Chunk vượt quá thời lượng audio")
        if start_ms < previous_end:
            raise ConflictError("CHUNK_OVERLAP", "Các chunk tự động bị chồng lấn")
        previous_end = end_ms
        validated.append((start_ms, end_ms))
    session.execute(delete(Chunk).where(Chunk.project_id == project_id))
    new_chunks: list[Chunk] = []
    for index, item in enumerate(items):
        label = str(item.get("speaker_label") or "SPEAKER_00")
        chunk = Chunk(
            project_id=project_id,
            speaker_id=speaker_ids_by_label.get(label),
            order_index=index,
            start_ms=validated[index][0],
            end_ms=validated[index][1],
            source="auto",
            status="draft",
            vad_confidence=float(item["vad_confidence"])
            if item.get("vad_confidence") is not None
            else None,
            diarization_confidence=(
                float(item["diarization_confidence"])
                if item.get("diarization_confidence") is not None
                else None
            ),
        )
        session.add(chunk)
        new_chunks.append(chunk)
    session.flush()
    for chunk in new_chunks:
        session.add(ChunkText(chunk_id=chunk.id, reference_status="missing"))
    project.active_revision += 1
    session.commit()
    return new_chunks
