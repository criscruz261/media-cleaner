import threading
from conftest import duplicate_group, scan
from app.hashing.sha256 import hash_file as real_hash
from app.database.models import ScanJob, CleanupOperation
from app.api.main import create_app
from fastapi.testclient import TestClient


def wait_worker(client):
    future = client.app.state.manager.active
    if future:
        future.result(timeout=10)


def test_pause_resume_and_cancel_real_worker(client, workspace, monkeypatch):
    (workspace / "a.MOV").write_bytes(b"video")
    (workspace / "a copy.MOV").write_bytes(b"video")
    started, release = threading.Event(), threading.Event()

    def controlled(path, expected, checkpoint):
        started.set()
        assert release.wait(5)
        checkpoint()
        return real_hash(path, expected, checkpoint)

    monkeypatch.setattr("app.workers.manager.hash_file", controlled)
    response = client.post("/api/v1/scans", json={"roots": [str(workspace)]})
    scan_id = response.json()["id"]
    assert started.wait(5)
    assert client.post(f"/api/v1/scans/{scan_id}/pause").json()["status"] == "paused"
    release.set()
    wait_worker(client)
    assert client.get(f"/api/v1/scans/{scan_id}").json()["status"] == "paused"
    assert client.post(f"/api/v1/scans/{scan_id}/resume").status_code == 200
    wait_worker(client)
    assert client.get(f"/api/v1/scans/{scan_id}").json()["status"] == "completed"

    started.clear()
    release.clear()
    (workspace / "b.MOV").write_bytes(b"other")
    (workspace / "b copy.MOV").write_bytes(b"other")
    response = client.post("/api/v1/scans", json={"roots": [str(workspace)]})
    scan_id = response.json()["id"]
    assert started.wait(5)
    assert client.post(f"/api/v1/scans/{scan_id}/cancel").json()["status"] == "cancelled"
    release.set()
    wait_worker(client)
    assert client.get(f"/api/v1/scans/{scan_id}").json()["status"] == "cancelled"


def test_disconnected_root_does_not_remove_history(client, workspace, monkeypatch):
    group = duplicate_group(client, workspace)
    old_id = group["scan_id"]
    from app.workers.manager import discover as real_discover

    def disconnect(root, *args):
        root.rename(root.with_name("disconnected"))
        yield from real_discover(root, *args)

    monkeypatch.setattr("app.workers.manager.discover", disconnect)
    job = scan(client, [workspace])
    assert job["errors"] >= 1
    assert job["status"] == "failed"
    assert client.get("/api/v1/scans/" + old_id).json()["status"] == "completed"
    assert client.get("/api/v1/groups?scan_id=" + old_id).json()["total"] == 1


def test_startup_marks_interrupted_jobs_and_cleanup(tmp_path):
    data = (tmp_path / "data").resolve()
    app = create_app(data, token="test")
    with TestClient(app, base_url="http://127.0.0.1:8765", headers={"Authorization": "Bearer test"}):
        with app.state.sessions.begin() as session:
            session.add(ScanJob(status="running", options={"roots": []}))
            session.add(
                CleanupOperation(
                    status="executing",
                    destination="quarantine",
                    token="test",
                    items=[],
                    total_bytes=0,
                    expires_at="2020-01-01T00:00:00+00:00",
                )
            )
    restarted = create_app(data, token="test")
    with TestClient(
        restarted, base_url="http://127.0.0.1:8765", headers={"Authorization": "Bearer test"}
    ) as client:
        assert client.get("/api/v1/scans").json()["items"][0]["status"] == "interrupted"
        assert client.get("/api/v1/cleanup/history").json()["items"][0]["status"] == "interrupted"
