from sqlalchemy.orm import Session

from jlpt_studio.api.schemas import ChunkUpdate, ProjectCreate
from jlpt_studio.db.models import Chunk, ChunkText, Speaker
from jlpt_studio.db.session import get_session_factory
from jlpt_studio.services.chunks import merge_chunks, split_chunk, update_chunk
from jlpt_studio.services.projects import create_project


def _seed(session: Session) -> tuple[Chunk, Chunk]:
    project = create_project(session, ProjectCreate(title="test"))
    speaker = Speaker(project_id=project.id, label="SPEAKER_00", display_name="A", color="#60a5fa")
    session.add(speaker)
    session.flush()
    first = Chunk(project_id=project.id, speaker_id=speaker.id, order_index=0, start_ms=0, end_ms=2000)
    second = Chunk(project_id=project.id, speaker_id=speaker.id, order_index=1, start_ms=2000, end_ms=4000)
    session.add_all([first, second])
    session.flush()
    session.add_all([ChunkText(chunk_id=first.id), ChunkText(chunk_id=second.id)])
    session.commit()
    return first, second


def test_split_merge_and_boundary_invalidation(isolated_db) -> None:
    with get_session_factory()() as session:
        first, second = _seed(session)
        left, right = split_chunk(session, first.id, 1000)
        assert left.end_ms == 1000
        assert right.start_ms == 1000
        assert right.end_ms == 2000
        merged = merge_chunks(session, [left.id, right.id])
        assert merged.start_ms == 0
        assert merged.end_ms == 2000
        updated = update_chunk(session, merged.id, ChunkUpdate(end_ms=1900))
        assert updated.end_ms == 1900
        assert session.get(ChunkText, updated.id).translation_status == "stale"
        assert session.get(Chunk, second.id) is not None

