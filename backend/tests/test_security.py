from app.database.models import ScanJob


def test_auth_and_origin(client):
    assert client.get("/api/v1/health", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 403
    assert (
        client.post(
            "/api/v1/scans", headers={"Origin": "https://evil.example"}, json={"roots": ["/"]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/session", headers={"Authorization": "Bearer wrong", "Origin": "http://127.0.0.1:8765"}
        ).status_code
        == 401
    )
    assert client.post("/api/v1/session").status_code == 200
    assert client.get("/api/v1/health", headers={"Authorization": ""}).status_code == 200
    assert client.put("/api/v1/settings", headers={"Authorization": ""}, json={}).status_code == 403


def test_pause_resume_cancel_states(client, workspace):
    # Deterministic persisted-job transition without relying on race-prone scan timing.
    with client.app.state.sessions.begin() as session:
        job = ScanJob(
            options={
                "roots": [str(workspace)],
                "mode": "exact",
                "excluded_directories": [],
                "excluded_extensions": [],
                "include_hidden": False,
                "protected_directories": [],
                "concurrency": 1,
            },
            status="paused",
        )
        session.add(job)
        session.flush()
        scan_id = job.id
    assert client.post(f"/api/v1/scans/{scan_id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/api/v1/scans/{scan_id}/resume").status_code == 400


def test_diagnostic_export_and_preview_id_restriction(client):
    response = client.get("/api/v1/diagnostics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert client.get("/api/v1/files/nonexistent/preview").status_code == 404
    assert (
        client.post(
            "/api/v1/cleanup/plan", json={"file_ids": ["arbitrary-id"], "destination": "permanent"}
        ).status_code
        == 422
    )
