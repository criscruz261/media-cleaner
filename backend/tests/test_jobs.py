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

    def controlled(path, expected, checkpoint, progress=None):
        started.set()
        assert release.wait(5)
        checkpoint()
        return real_hash(path, expected, checkpoint, progress)

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


def test_live_matches_survive_reconnect_and_resume_skips_checkpoints(client, workspace, monkeypatch):
    import time
    from app.database.models import File
    from sqlalchemy import select
    from test_similarity import sample

    image = sample(workspace / "original.png")
    (workspace / "copy.png").write_bytes((workspace / "original.png").read_bytes())
    image.resize((120, 80)).save(workspace / "resized.jpg", quality=90)
    (workspace / "waiting.MOV").write_bytes(b"waiting")
    manager = client.app.state.manager
    original = manager.process_file
    release = threading.Event()
    hashed = []

    def hash_count(path, expected, checkpoint, progress=None):
        hashed.append(path.name)
        return real_hash(path, expected, checkpoint, progress)

    def controlled(scan_id, file_id, checkpoint):
        with manager.sessions() as session:
            name = session.get(File, file_id).name
        if name == "waiting.MOV":
            while not release.wait(0.01):
                checkpoint()
        return original(scan_id, file_id, checkpoint)

    monkeypatch.setattr(manager, "process_file", controlled)
    monkeypatch.setattr("app.workers.manager.hash_file", hash_count)
    response = client.post(
        "/api/v1/scans", json={"roots": [str(workspace)], "mode": "similar", "concurrency": 2}
    )
    assert response.status_code == 201
    scan_id = response.json()["id"]
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            matches = client.get(f"/api/v1/scans/{scan_id}/matches").json()
            if matches["exact_groups"] == 1 and matches["similar_groups"] == 1:
                break
            time.sleep(0.01)
        else:
            raise AssertionError(matches)
        assert matches["provisional"]
        group_id = matches["items"][0]["id"]
        assert client.post(f"/api/v1/groups/{group_id}/review", json={"changes": {}}).status_code == 400
        job = client.get(f"/api/v1/scans/{scan_id}").json()
        assert job["status"] == "running"
        assert job["processed"] == 3
        assert 0 < job["bytes_processed"] < job["total_bytes"]
        assert job["checkpoint_at"]
        assert client.get("/api/v1/scans/active").json()["scan"]["id"] == scan_id
        assert client.get("/api/v1/scans").json()["total"] == 1
        assert client.post(f"/api/v1/scans/{scan_id}/pause").status_code == 200
        wait_worker(client)
        before = list(hashed)
        assert len(before) == 3
        release.set()
        assert client.post(f"/api/v1/scans/{scan_id}/resume").status_code == 200
        wait_worker(client)
        job = client.get(f"/api/v1/scans/{scan_id}").json()
        assert job["status"] == "completed", job
        assert job["processed"] == 4
        assert job["bytes_processed"] == job["total_bytes"]
        assert sorted(hashed) == sorted(before + ["waiting.MOV"])
        assert not client.get(f"/api/v1/scans/{scan_id}/matches").json()["provisional"]
        assert client.get("/api/v1/scans/active").json()["scan"] is None
        with manager.sessions() as session:
            assert len(session.scalars(select(File).where(File.scan_id == scan_id)).all()) == 4
    finally:
        release.set()


def test_backend_restart_reuses_durable_completed_file_checkpoints(client, workspace, monkeypatch):
    from app.database.models import ScanJob
    from test_similarity import sample

    sample(workspace / "original.png")
    (workspace / "copy.png").write_bytes((workspace / "original.png").read_bytes())
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed"
    with client.app.state.sessions.begin() as session:
        session.get(ScanJob, job["id"]).status = "running"
        database_path = session.bind.url.database
    from pathlib import Path

    restarted = create_app(Path(database_path).parent, token="restart-test")

    def unexpected(*args, **kwargs):
        raise AssertionError("Completed checkpoints must not re-read media")

    monkeypatch.setattr("app.workers.manager.hash_file", unexpected)
    monkeypatch.setattr("app.workers.manager.extract", unexpected)
    monkeypatch.setattr("app.workers.manager.fingerprint_image", unexpected)
    with TestClient(
        restarted, base_url="http://127.0.0.1:8765", headers={"Authorization": "Bearer restart-test"}
    ) as recovered:
        state = recovered.get("/api/v1/scans/active").json()["scan"]
        assert state["id"] == job["id"]
        assert state["status"] == "interrupted"
        assert state["processed"] == 2
        assert recovered.get(f"/api/v1/scans/{job['id']}/matches").json()["exact_groups"] == 1
        assert recovered.post(f"/api/v1/scans/{job['id']}/resume").status_code == 200
        wait_worker(recovered)
        state = recovered.get(f"/api/v1/scans/{job['id']}").json()
        assert state["status"] == "completed"
        assert state["processed"] == 2
        assert state["errors"] == 0
        assert state["bytes_processed"] == job["bytes_processed"]
