from __future__ import annotations

import random
from typing import Literal

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import (
    AnswerBundle,
    AttemptCreate,
    AttemptRead,
    ExerciseAnswerRead,
    ExerciseRead,
    ExerciseUpdate,
)
from jlpt_studio.core.errors import NotFoundError, StudioError
from jlpt_studio.db.models import Attempt, Chunk, ChunkText, Exercise
from jlpt_studio.japanese import (
    character_diff,
    generate_blank_spec,
    normalize_japanese,
    similarity_score,
)
from jlpt_studio.services.chunks import chunk_to_read
from jlpt_studio.services.projects import get_project_or_404


def _redacted_blank_spec(exercise: Exercise) -> dict[str, object]:
    """Return cloze metadata without shipping token surfaces to the browser."""
    if exercise.mode != "cloze":
        return {}
    indexes = exercise.blank_spec_json.get("blank_token_indexes", [])
    return {
        "version": exercise.blank_spec_json.get("version", 1),
        "blank_count": len(indexes) if isinstance(indexes, list) else 0,
        "blank_token_indexes": indexes if isinstance(indexes, list) else [],
    }


def _exercise_to_read(session: Session, exercise: Exercise) -> ExerciseRead:
    chunk = session.get(Chunk, exercise.chunk_id)
    chunk_text = session.get(ChunkText, exercise.chunk_id)
    safe_chunk = chunk_to_read(session, chunk).model_copy(update={"text": None}) if chunk else None
    return ExerciseRead(
        id=exercise.id,
        project_id=exercise.project_id,
        chunk_id=exercise.chunk_id,
        mode=exercise.mode,
        blank_spec=_redacted_blank_spec(exercise),
        settings=exercise.settings_json,
        reference_revision=exercise.reference_revision,
        status=exercise.status,
        is_difficult=exercise.is_difficult,
        reference_status=chunk_text.reference_status if chunk_text else "missing",
        chunk=safe_chunk,
    )


def _answer_bundle(session: Session, exercise: Exercise) -> AnswerBundle:
    text = session.get(ChunkText, exercise.chunk_id)
    if text is None or not text.reference_text:
        raise StudioError("REFERENCE_MISSING", "Bài luyện chưa có đáp án transcript", status_code=422)
    tokens = text.furigana_json
    expected = _cloze_expected(exercise) if exercise.mode == "cloze" else []
    return AnswerBundle(
        reference_text=text.reference_text,
        furigana=tokens,
        translation_vi=text.translation_vi,
        cloze_expected=expected,
        reference_confirmed=text.reference_status == "user_confirmed",
    )


def exercise_answer(session: Session, exercise_id: str) -> ExerciseAnswerRead:
    exercise = get_exercise_or_404(session, exercise_id)
    bundle = _answer_bundle(session, exercise)
    blank_spec = dict(exercise.blank_spec_json)
    # Answer endpoint is the explicit reveal boundary, so token surfaces are allowed here.
    return ExerciseAnswerRead(
        exercise_id=exercise.id,
        chunk_id=exercise.chunk_id,
        mode=exercise.mode,
        reference_text=bundle.reference_text,
        furigana=bundle.furigana,
        translation_vi=bundle.translation_vi,
        blank_spec=blank_spec,
        reference_confirmed=bundle.reference_confirmed,
    )


def generate_exercises(
    session: Session,
    project_id: str,
    *,
    mode: Literal["full", "cloze"],
    chunk_ids: list[str] | None,
    settings: dict[str, object],
) -> list[ExerciseRead]:
    project = get_project_or_404(session, project_id)
    chunks_query = select(Chunk).where(Chunk.project_id == project_id).order_by(Chunk.order_index)
    if chunk_ids:
        chunks_query = chunks_query.where(Chunk.id.in_(chunk_ids))
    chunks = session.scalars(chunks_query).all()
    if settings.get("randomize"):
        random.Random(int(settings.get("seed", 0))).shuffle(chunks)
    if not chunks:
        raise StudioError("NO_CHUNKS", "Không có chunk phù hợp để tạo bài luyện", status_code=422)
    valid: list[tuple[Chunk, ChunkText]] = []
    for chunk in chunks:
        text = session.get(ChunkText, chunk.id)
        if text and text.reference_text:
            valid.append((chunk, text))
    if not valid:
        raise StudioError(
            "NO_REFERENCE_TEXT", "Cần có transcript trước khi tạo bài luyện", status_code=422
        )
    selected_ids = [chunk.id for chunk, _ in valid]
    session.execute(
        delete(Exercise).where(
            Exercise.project_id == project_id,
            Exercise.mode == mode,
            Exercise.chunk_id.in_(selected_ids),
        )
    )
    created: list[Exercise] = []
    for chunk, text in valid:
        blank_spec: dict[str, object] = {}
        if mode == "cloze":
            tokens = text.furigana_json
            if not tokens:
                raise StudioError(
                    "FURIGANA_REQUIRED",
                    "Cần chạy furigana trước khi tạo bài điền chỗ trống.",
                    status_code=422,
                )
            blank_spec = generate_blank_spec(
                tokens,
                count=int(settings.get("blank_count", 1)),
                grammar_mode=bool(settings.get("grammar_mode", False)),
                seed=int(settings["seed"]) if settings.get("seed") is not None else None,
            )
            blank_spec["tokens"] = tokens
        exercise = Exercise(
            project_id=project_id,
            chunk_id=chunk.id,
            mode=mode,
            blank_spec_json=blank_spec,
            settings_json=settings,
            reference_revision=project.active_revision,
            status="ready",
        )
        session.add(exercise)
        created.append(exercise)
    session.commit()
    return [_exercise_to_read(session, item) for item in created]


def list_exercises(
    session: Session, project_id: str, mode: str | None = None
) -> list[ExerciseRead]:
    get_project_or_404(session, project_id)
    query = (
        select(Exercise)
        .where(Exercise.project_id == project_id, Exercise.status == "ready")
        .order_by(Exercise.created_at)
    )
    if mode:
        query = query.where(Exercise.mode == mode)
    return [_exercise_to_read(session, exercise) for exercise in session.scalars(query).all()]


def get_exercise_or_404(session: Session, exercise_id: str) -> Exercise:
    exercise = session.get(Exercise, exercise_id)
    if not exercise:
        raise NotFoundError("Không tìm thấy bài luyện")
    return exercise


def update_exercise(session: Session, exercise_id: str, payload: ExerciseUpdate) -> Exercise:
    exercise = get_exercise_or_404(session, exercise_id)
    if payload.blank_spec is not None:
        if exercise.mode != "cloze":
            raise StudioError("NOT_CLOZE_EXERCISE", "Chỉ bài cloze mới có blank spec")
        tokens = exercise.blank_spec_json.get("tokens", [])
        requested = payload.blank_spec.get("blank_token_indexes", [])
        if not isinstance(requested, list) or any(
            not isinstance(index, int) or index < 0 or index >= len(tokens) for index in requested
        ):
            raise StudioError("INVALID_BLANK_SPEC", "Vị trí blank không hợp lệ")
        exercise.blank_spec_json = {
            **exercise.blank_spec_json,
            "blank_token_indexes": sorted(set(requested)),
        }
    if payload.is_difficult is not None:
        exercise.is_difficult = payload.is_difficult
    session.commit()
    return exercise


def _cloze_expected(exercise: Exercise) -> list[str]:
    tokens = exercise.blank_spec_json.get("tokens", [])
    indices = exercise.blank_spec_json.get("blank_token_indexes", [])
    return [str(tokens[index].get("surface", "")) for index in indices]


def submit_attempt(session: Session, exercise_id: str, payload: AttemptCreate) -> AttemptRead:
    exercise = get_exercise_or_404(session, exercise_id)
    chunk_text = session.get(ChunkText, exercise.chunk_id)
    expected_text = chunk_text.reference_text if chunk_text else None
    if not expected_text:
        raise StudioError(
            "REFERENCE_MISSING", "Bài luyện không còn đáp án transcript", status_code=422
        )
    if exercise.mode == "cloze":
        expected = _cloze_expected(exercise)
        answers = payload.blank_answers or [payload.answer_text]
        normalized_expected = [normalize_japanese(value) for value in expected]
        normalized_answers = [normalize_japanese(value) for value in answers]
        individual = [
            similarity_score(
                expected_value, normalized_answers[index] if index < len(normalized_answers) else ""
            )
            for index, expected_value in enumerate(normalized_expected)
        ]
        score = round(sum(individual) / len(individual), 2) if individual else 0.0
        strict_individual = [
            similarity_score(expected_value, answers[index] if index < len(answers) else "")
            for index, expected_value in enumerate(expected)
        ]
        strict_score = (
            round(sum(strict_individual) / len(strict_individual), 2) if strict_individual else 0.0
        )
        diff = [
            {
                "kind": "blank",
                "index": str(index),
                "expected": expected_value,
                "actual": answers[index] if index < len(answers) else "",
                "score": str(individual[index]),
            }
            for index, expected_value in enumerate(expected)
        ]
        answer_text = "\u241f".join(answers)
        normalized_answer = "\u241f".join(normalized_answers)
    else:
        normalized_expected_text = normalize_japanese(expected_text)
        normalized_answer = normalize_japanese(payload.answer_text)
        score = similarity_score(normalized_expected_text, normalized_answer)
        strict_score = similarity_score(
            normalize_japanese(expected_text, forgiving=False),
            normalize_japanese(payload.answer_text, forgiving=False),
        )
        diff = character_diff(normalized_expected_text, normalized_answer)
        answer_text = payload.answer_text
    attempt = Attempt(
        exercise_id=exercise.id,
        answer_text=answer_text,
        normalized_answer=normalized_answer,
        score=None if payload.revealed_answer else score,
        strict_score=None if payload.revealed_answer else strict_score,
        diff_json=diff,
        revealed_answer=payload.revealed_answer,
        duration_ms=payload.duration_ms,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return AttemptRead(
        id=attempt.id,
        exercise_id=attempt.exercise_id,
        answer_text=attempt.answer_text,
        score=attempt.score,
        strict_score=attempt.strict_score,
        diff=attempt.diff_json,
        revealed_answer=attempt.revealed_answer,
        duration_ms=attempt.duration_ms,
        created_at=attempt.created_at,
        # Checking an attempt is the first answer boundary. The exercise list
        # stays redacted; once submitted, the learner is allowed to inspect the
        # atomic Japanese/furigana/translation bundle.
        answer=_answer_bundle(session, exercise),
    )


def project_stats(session: Session, project_id: str) -> dict[str, float | int]:
    get_project_or_404(session, project_id)
    exercise_count = (
        session.scalar(select(func.count(Exercise.id)).where(Exercise.project_id == project_id))
        or 0
    )
    attempt_count = (
        session.scalar(
            select(func.count(Attempt.id))
            .join(Exercise, Attempt.exercise_id == Exercise.id)
            .where(Exercise.project_id == project_id)
        )
        or 0
    )
    average_score = session.scalar(
        select(func.avg(Attempt.score))
        .join(Exercise, Attempt.exercise_id == Exercise.id)
        .where(Exercise.project_id == project_id)
    )
    difficult_count = (
        session.scalar(
            select(func.count(Exercise.id)).where(
                Exercise.project_id == project_id, Exercise.is_difficult.is_(True)
            )
        )
        or 0
    )
    return {
        "exercise_count": exercise_count,
        "attempt_count": attempt_count,
        "average_score": round(float(average_score or 0), 2),
        "difficult_count": difficult_count,
    }
