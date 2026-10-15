import pytest
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


@pytest.mark.parametrize("resume_after_cleanup", [False, True])
def test_live_matches_survive_reconnect_and_resume_skips_checkpoints(
    client, workspace, monkeypatch, resume_after_cleanup
):
    import time
    from app.database.models import File
    from sqlalchemy import select
    from test_similarity import sample

    image = sample(workspace / "original.png")
    (workspace / "copy.png").write_bytes((workspace / "original.png").read_bytes())
    image.resize((120, 80)).save(workspace / "resized.jpg", quality=90)
    (workspace / "waiting.png").write_bytes((workspace / "original.png").read_bytes())
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
        if name == "waiting.png":
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
        exact = next(group for group in matches["items"] if group["classification"] == "EXACT_DUPLICATE")
        similar = next(group for group in matches["items"] if group["classification"] == "SIMILAR_CONTENT")
        members = client.get(f"/api/v1/groups/{exact['id']}").json()["files"]
        unwanted = next(file for file in members if file["name"] == "copy.png")
        similar_members = client.get(f"/api/v1/groups/{similar['id']}").json()["files"]
        resized = next(file for file in similar_members if file["name"] == "resized.jpg")
        assert (
            client.post(
                f"/api/v1/groups/{similar['id']}/review", json={"changes": {resized["id"]: False}}
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/groups/{exact['id']}/review", json={"changes": {unwanted["id"]: False}}
            ).status_code
            == 200
        )
        preview = client.post(
            "/api/v1/cleanup/plan",
            json={"file_ids": [unwanted["id"]], "group_id": exact["id"], "destination": "quarantine"},
        )
        assert preview.status_code == 201, preview.text
        plan = preview.json()
        payload = {"plan_id": plan["id"], "token": plan["token"], "confirmed": False}
        assert client.post("/api/v1/cleanup/execute", json=payload).status_code == 400
        assert (workspace / "copy.png").exists()
        payload["confirmed"] = True
        outcome = client.post("/api/v1/cleanup/execute", json=payload)
        assert outcome.status_code == 200, outcome.text
        assert outcome.json()["status"] == "completed"
        assert not (workspace / "copy.png").exists()
        job = client.get(f"/api/v1/scans/{scan_id}").json()
        assert job["status"] == "running"
        assert job["processed"] == 3
        assert 0 < job["bytes_processed"] < job["total_bytes"]
        assert job["checkpoint_at"]
        assert client.get("/api/v1/scans/active").json()["scan"]["id"] == scan_id
        assert client.get("/api/v1/scans").json()["total"] == 1
        if resume_after_cleanup:
            assert client.post(f"/api/v1/scans/{scan_id}/pause").status_code == 200
            wait_worker(client)
        before = list(hashed)
        assert len(before) == 3
        release.set()
        if resume_after_cleanup:
            assert client.post(f"/api/v1/scans/{scan_id}/resume").status_code == 200
        wait_worker(client)
        job = client.get(f"/api/v1/scans/{scan_id}").json()
        assert job["status"] == "completed", job
        assert job["processed"] == 4
        assert job["bytes_processed"] == job["total_bytes"]
        assert sorted(hashed) == sorted(before + ["waiting.png"])
        assert not client.get(f"/api/v1/scans/{scan_id}/matches").json()["provisional"]
        assert client.get("/api/v1/scans/active").json()["scan"] is None
        final = client.get(f"/api/v1/scans/{scan_id}/matches").json()
        assert final["exact_groups"] == 1
        assert final["similar_groups"] == 1
        for group in final["items"]:
            files = client.get(f"/api/v1/groups/{group['id']}").json()["files"]
            assert all(file["name"] != "copy.png" for file in files)
            assert next(file for file in files if file["name"] == "waiting.png")["keep"]
            if group["classification"] == "SIMILAR_CONTENT":
                assert not next(file for file in files if file["name"] == "resized.jpg")["keep"]
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
    from sqlalchemy import text

    group = client.get(f"/api/v1/scans/{job['id']}/matches").json()["items"][0]
    files = client.get(f"/api/v1/groups/{group['id']}").json()["files"]
    copy_id = next(file["id"] for file in files if file["name"] == "copy.png")
    assert (
        client.post(f"/api/v1/groups/{group['id']}/review", json={"changes": {copy_id: False}}).status_code
        == 200
    )
    with client.app.state.sessions.begin() as session:
        # Model an existing 0003 database: migration must import reviewed group choices.
        session.execute(text("DROP TABLE file_review_choices"))
        session.execute(text("UPDATE alembic_version SET version_num='0003'"))
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
        group = recovered.get(f"/api/v1/scans/{job['id']}/matches").json()["items"][0]
        files = recovered.get(f"/api/v1/groups/{group['id']}").json()["files"]
        assert not next(file for file in files if file["id"] == copy_id)["keep"]


def test_rebuilt_groups_restore_late_members_without_overwriting_new_choices(client, workspace):
    from app.grouping.live import LiveMatcher

    for name in ["a.MOV", "b.MOV", "c.MOV", "d.MOV"]:
        (workspace / name).write_bytes(b"same video")
    job = scan(client, [workspace])
    group = client.get(f"/api/v1/scans/{job['id']}/matches").json()["items"][0]
    files = client.get(f"/api/v1/groups/{group['id']}").json()["files"]
    ids = {file["name"]: file["id"] for file in files}
    assert (
        client.post(
            f"/api/v1/groups/{group['id']}/review", json={"changes": {ids["c.MOV"]: False}}
        ).status_code
        == 200
    )
    matcher = LiveMatcher(client.app.state.sessions, job["id"], {"mode": "exact"}, lambda: None)
    try:
        matcher.add(ids["a.MOV"])
        matcher.add(ids["b.MOV"])
        rebuilt = client.get(f"/api/v1/scans/{job['id']}/matches").json()["items"][0]
        assert (
            client.post(
                f"/api/v1/groups/{rebuilt['id']}/review", json={"changes": {ids["a.MOV"]: False}}
            ).status_code
            == 200
        )
        matcher.add(ids["c.MOV"])
        matcher.add(ids["d.MOV"])
        matcher.finish()
        files = client.get(f"/api/v1/groups/{rebuilt['id']}").json()["files"]
        assert {file["name"]: file["keep"] for file in files} == {
            "a.MOV": False,
            "b.MOV": True,
            "c.MOV": False,
            "d.MOV": True,
        }
    finally:
        matcher.close()
