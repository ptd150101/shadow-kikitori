from __future__ import annotations

from fastapi.testclient import TestClient

from jlpt_studio.db.models import Chunk, ChunkText, MediaAsset
from jlpt_studio.db.session import get_session_factory


def test_practice_payload_redacts_answers_until_explicit_reveal(client: TestClient) -> None:
    project = client.post("/api/projects", json={"title": "Practice", "source_type": "upload"}).json()
    project_id = project["id"]
    with get_session_factory()() as session:
        session.add(MediaAsset(project_id=project_id, kind="playback", relative_path="audio.opus", duration_ms=3000))
        chunk = Chunk(project_id=project_id, order_index=0, start_ms=0, end_ms=2500, source="manual", status="draft")
        session.add(chunk)
        session.flush()
        session.add(ChunkText(chunk_id=chunk.id, reference_text="明日学校へ行きます。", reference_status="user_confirmed", furigana_json=[{"surface": "明日", "reading": "あした", "ruby": True, "part_of_speech": "名詞"}], furigana_status="ready"))
        session.commit()
    generated = client.post(f"/api/projects/{project_id}/exercises/generate", json={"mode": "cloze"})
    assert generated.status_code == 201
    exercise = generated.json()[0]
    assert exercise["chunk"]["text"] is None
    assert "tokens" not in exercise["blank_spec"]
    assert "reference_text" not in str(exercise)
    exercise_id = exercise["id"]
    checked = client.post(f"/api/exercises/{exercise_id}/attempts", json={"blank_answers": ["明日"]})
    assert checked.status_code == 201
    assert checked.json()["answer"]["reference_text"] == "明日学校へ行きます。"
    answer = client.get(f"/api/exercises/{exercise_id}/answer")
    assert answer.status_code == 200
    assert answer.json()["reference_text"] == "明日学校へ行きます。"
    revealed = client.post(f"/api/exercises/{exercise_id}/attempts", json={"revealed_answer": True})
    assert revealed.status_code == 201
    assert revealed.json()["answer"]["reference_text"] == "明日学校へ行きます。"


def test_practice_chunks_and_speaker_endpoints_are_safe(client: TestClient) -> None:
    project = client.post("/api/projects", json={"title": "Metadata", "source_type": "upload"}).json()
    project_id = project["id"]
    with get_session_factory()() as session:
        chunk = Chunk(project_id=project_id, order_index=0, start_ms=0, end_ms=1000)
        session.add(chunk)
        session.flush()
        session.add(ChunkText(chunk_id=chunk.id, reference_text="秘密", reference_status="user_confirmed"))
        session.commit()
    safe = client.get(f"/api/projects/{project_id}/practice-chunks")
    assert safe.status_code == 200
    assert safe.json()[0]["text"] is None
    speaker = client.post(f"/api/projects/{project_id}/speakers", json={"label": "SPEAKER_00", "display_name": "Người nói"})
    assert speaker.status_code == 201
    assert client.get(f"/api/projects/{project_id}/speakers").json()[0]["display_name"] == "Người nói"
