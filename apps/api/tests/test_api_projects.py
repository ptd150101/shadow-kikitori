from fastapi.testclient import TestClient


def test_project_crud_and_job_queue(client: TestClient) -> None:
    created = client.post("/api/projects", json={"title": "JLPT sample", "source_type": "upload"})
    assert created.status_code == 201
    project = created.json()
    assert project["title"] == "JLPT sample"
    listed = client.get("/api/projects")
    assert len(listed.json()) == 1
    updated = client.patch(f"/api/projects/{project['id']}", json={"title": "Updated"})
    assert updated.json()["title"] == "Updated"
    missing_process = client.post(f"/api/projects/{project['id']}/process", json={})
    assert missing_process.status_code == 404
    deleted = client.delete(f"/api/projects/{project['id']}")
    assert deleted.status_code == 204


def test_capabilities_endpoint(client: TestClient) -> None:
    response = client.get("/api/system/capabilities")
    assert response.status_code == 200
    assert "ffmpeg" in response.json()

