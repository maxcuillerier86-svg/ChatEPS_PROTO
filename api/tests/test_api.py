from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_pseudo_chat_conversation_create():
    headers = {"X-Pseudo": "TestPseudo"}
    r = client.post("/chat/conversations", headers=headers, json={"title": "Fil Test", "mode": "co_design"})
    assert r.status_code == 200
    assert r.json()["title"] == "Fil Test"


def test_artifact_versioning_with_pseudo():
    headers = {"X-Pseudo": "ArtifactPseudo"}
    created = client.post("/artefacts", headers=headers, json={"title": "Plan A", "content_md": "v1"}).json()
    updated = client.post(f"/artefacts/{created['id']}/versions", headers=headers, json={"content_md": "v2", "status": "soumis"})
    assert updated.status_code == 200
    versions = client.get(f"/artefacts/{created['id']}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) >= 2
