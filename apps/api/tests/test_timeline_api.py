from __future__ import annotations

from fastapi.testclient import TestClient

from jlpt_studio.core.config import get_settings
from jlpt_studio.db.models import Chunk, MediaAsset
from jlpt_studio.db.session import get_session_factory


def test_timeline_reorder_delete_and_range_stream(client: TestClient) -> None:
    project = client.post("/api/projects", json={"title": "Timeline", "source_type": "upload"}).json()
    project_id = project["id"]
    with get_session_factory()() as session:
        playback = get_settings().resolved_data_dir / "projects" / project_id / "normalized" / "playback.opus"
        playback.parent.mkdir(parents=True, exist_ok=True)
        playback.write_bytes(b"0123456789")
        session.add(MediaAsset(project_id=project_id, kind="playback", relative_path=f"projects/{project_id}/normalized/playback.opus", duration_ms=5000))
        session.add_all([
            Chunk(project_id=project_id, order_index=0, start_ms=0, end_ms=1000),
            Chunk(project_id=project_id, order_index=1, start_ms=1000, end_ms=2000),
        ])
        session.commit()
        ids = [item.id for item in session.query(Chunk).filter_by(project_id=project_id).order_by(Chunk.order_index)]
    current = client.get(f"/api/projects/{project_id}/timeline").json()
    reordered = client.post(f"/api/projects/{project_id}/chunks/reorder", json={"ordered_chunk_ids": list(reversed(ids)), "expected_project_revision": current["revision"]})
    assert reordered.status_code == 200
    assert [item["id"] for item in reordered.json()] == list(reversed(ids))
    ranged = client.get(f"/api/projects/{project_id}/media/stream", headers={"Range": "bytes=2-5"})
    assert ranged.status_code == 206
    assert ranged.content == b"2345"
    assert client.delete(f"/api/chunks/{ids[0]}").status_code == 204
