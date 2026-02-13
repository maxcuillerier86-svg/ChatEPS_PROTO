from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def register_and_login(email: str):
    client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": "secret123", "role": "student"},
    )
    token = client.post("/auth/login", json={"email": email, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_auth_me():
    headers = register_and_login("auth_test@local.dev")
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "auth_test@local.dev"


def test_artifact_versioning():
    headers = register_and_login("artifact_test@local.dev")
    created = client.post("/artefacts", headers=headers, json={"title": "Plan A", "content_md": "v1"}).json()
    updated = client.post(f"/artefacts/{created['id']}/versions", headers=headers, json={"content_md": "v2", "status": "soumis"})
    assert updated.status_code == 200
    versions = client.get(f"/artefacts/{created['id']}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) >= 2
