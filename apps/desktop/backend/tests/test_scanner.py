import hashlib
import os
from PIL import Image
from sqlalchemy import inspect, text
from app.api.main import create_app
from app.core.filesystem import identity
from app.hashing.sha256 import hash_file
from conftest import scan
from fastapi.testclient import TestClient


def test_streaming_hash_and_change_detection(workspace):
    path = workspace / "large.MOV"
    path.write_bytes(b"abc" * 500_000)
    snapshot = identity(path)
    assert hash_file(path, snapshot) == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b"changed")
    import pytest

    with pytest.raises(ValueError):
        hash_file(path, snapshot)


def test_recursive_multi_root_exact_and_incremental(client, workspace):
    nested = workspace / "nested"
    nested.mkdir()
    other = workspace.parent / "external"
    other.mkdir()
    Image.new("RGB", (20, 10), "red").save(workspace / "original.png")
    (nested / "original copy.PNG").write_bytes((workspace / "original.png").read_bytes())
    (other / "renamed.png").write_bytes((workspace / "original.png").read_bytes())
    (workspace / "not-media.txt").write_bytes(b"ignored")
    (workspace / "corrupt.jpg").write_bytes(b"corrupt")
    first = scan(client, [workspace, other])
    assert first["status"] == "completed"
    assert first["discovered"] == 4
    groups = client.get(f"/api/v1/groups?scan_id={first['id']}").json()
    assert groups["total"] == 1
    assert groups["items"][0]["member_count"] == 3
    detail = client.get("/api/v1/groups/" + groups["items"][0]["id"]).json()
    assert all(file["metadata"]["width"] == 20 for file in detail["files"])
    assert detail["classification"] == "EXACT_DUPLICATE"
    second = scan(client, [workspace, other])
    assert second["status"] == "completed"
    assert second["cache_hits"] == 4
    assert client.get("/api/v1/scans").json()["total"] == 2


def test_exclusions_hidden_hardlinks_and_symlink_loops(client, workspace):
    (workspace / "one.MOV").write_bytes(b"video")
    (workspace / "one copy.MOV").write_bytes(b"video")
    (workspace / ".hidden.MOV").write_bytes(b"video")
    os.link(workspace / "one.MOV", workspace / "hardlink.MOV")
    (workspace / "loop").symlink_to(workspace, target_is_directory=True)
    excluded = workspace / "excluded"
    excluded.mkdir()
    (excluded / "ignored.MOV").write_bytes(b"video")
    job = scan(client, [workspace, workspace], excluded_directories=[str(excluded)])
    assert job["status"] == "completed"
    assert job["discovered"] == 2
    hidden = scan(client, [workspace], include_hidden=True, excluded_directories=[str(excluded)])
    assert hidden["discovered"] == 3
    none = scan(client, [workspace], excluded_extensions=["MOV"])
    assert none["discovered"] == 0


def test_database_migration_wal_and_restart(tmp_path, workspace):
    data = (tmp_path / "persistent").resolve()
    (workspace / "a.jpg").write_bytes(b"first")
    with TestClient(
        create_app(data, token="test"),
        base_url="http://127.0.0.1:8765",
        headers={"Authorization": "Bearer test"},
    ) as client:
        job = scan(client, [workspace])
        with client.app.state.sessions() as session:
            assert session.execute(text("PRAGMA journal_mode")).scalar() == "wal"
            assert session.execute(text("PRAGMA foreign_keys")).scalar() == 1
            assert session.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0005"
            assert len(inspect(session.bind).get_table_names()) == 14  # 13 domain tables + migration version
    with TestClient(
        create_app(data, token="test"),
        base_url="http://127.0.0.1:8765",
        headers={"Authorization": "Bearer test"},
    ) as client:
        assert client.get("/api/v1/scans/" + job["id"]).json()["status"] == "completed"


def test_image_preview_and_range_video(client, workspace):
    Image.new("RGB", (40, 20), "blue").save(workspace / "one.png")
    (workspace / "clip.MOV").write_bytes(b"0123456789")
    job = scan(client, [workspace])
    files = client.get(f"/api/v1/files?scan_id={job['id']}").json()["items"]
    for file in files:
        url = "/api/v1/files/" + file["id"] + "/preview"
        if file["media_type"] == "image":
            response = client.get(url)
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
        else:
            response = client.get(url, headers={"Range": "bytes=2-4"})
            assert response.status_code == 206
            assert response.content == b"234"
            assert response.headers["content-range"] == "bytes 2-4/10"


def test_thumbnails_are_cached_and_reject_changed_sources(client, workspace, monkeypatch):
    from PIL import Image
    from app.metadata.thumbnails import thumbnail
    from conftest import scan

    (workspace / "clip.MOV").write_bytes(b"synthetic")
    calls = []

    def frame(path, timestamp):
        calls.append(path)
        return Image.new("RGB", (640, 360), "green")

    monkeypatch.setattr("app.metadata.thumbnails.sample_video_frame", frame)
    thumbnail.cache_clear()
    job = scan(client, [workspace])
    file = client.get(f"/api/v1/files?scan_id={job['id']}").json()["items"][0]
    url = f"/api/v1/files/{file['id']}/thumbnail"
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    from io import BytesIO

    assert Image.open(BytesIO(response.content)).width <= 480
    assert client.get(url).content == response.content
    assert len(calls) == 1
    (workspace / "clip.MOV").write_bytes(b"changed")
    assert client.get(url).status_code == 409
    assert client.get("/api/v1/files/missing/thumbnail").status_code == 404
    thumbnail.cache_clear()


def test_saved_results_previews_survive_drive_device_change(client, workspace):
    from app.database.models import File
    from app.core.filesystem import stored_identity
    from conftest import duplicate_group

    Image.new("RGB", (80, 60), "green").save(workspace / "photo.png")
    job = scan(client, [workspace])
    file = client.get(f"/api/v1/files?scan_id={job['id']}").json()["items"][0]
    with client.app.state.sessions.begin() as session:
        saved = session.get(File, file["id"])
        saved.device = "previous-mount-device"

    for endpoint in ("thumbnail", "preview"):
        response = client.get(f"/api/v1/files/{file['id']}/{endpoint}")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "image/jpeg"
    with client.app.state.sessions() as session:
        saved = session.get(File, file["id"])
        assert saved.device == "previous-mount-device"
        assert stored_identity(saved) != identity(workspace / "photo.png")

    # Cleanup still uses the full saved identity, including device number.
    group = duplicate_group(client, workspace)
    unwanted = next(file for file in group["files"] if file["id"] != group["recommended_id"])
    with client.app.state.sessions.begin() as session:
        session.get(File, unwanted["id"]).device = "previous-mount-device"
    response = client.post(
        "/api/v1/cleanup/plan",
        json={"file_ids": [unwanted["id"]], "group_id": group["id"], "destination": "quarantine"},
    )
    assert response.status_code == 400


def test_saved_results_previews_reject_other_identity_changes(client, workspace):
    from app.database.models import File

    path = workspace / "photo.png"
    Image.new("RGB", (80, 60), "green").save(path)
    job = scan(client, [workspace])
    file = client.get(f"/api/v1/files?scan_id={job['id']}").json()["items"][0]
    for field in ("inode", "size", "mtime_ns", "ctime_ns"):
        with client.app.state.sessions.begin() as session:
            saved = session.get(File, file["id"])
            original = getattr(saved, field)
            setattr(saved, field, original + 1 if isinstance(original, int) else str(int(original) + 1))
        for endpoint in ("thumbnail", "preview"):
            assert client.get(f"/api/v1/files/{file['id']}/{endpoint}").status_code == 409
        with client.app.state.sessions.begin() as session:
            setattr(session.get(File, file["id"]), field, original)
    path.unlink()
    for endpoint in ("thumbnail", "preview"):
        assert client.get(f"/api/v1/files/{file['id']}/{endpoint}").status_code == 404


def test_system_trash_and_empty_media_are_always_excluded(client, workspace):
    (workspace / "original.mp4").write_bytes(b"video")
    (workspace / "original copy.mp4").write_bytes(b"video")
    (workspace / "empty.mp4").touch()
    (workspace / "empty copy.mp4").touch()
    for directory in [
        "$RECYCLE.BIN",
        "$recycle.bin",
        "RECYCLER",
        "RECYCLED",
        ".Trash",
        ".Trashes",
        ".Trash-1000",
    ]:
        trash = workspace / directory
        trash.mkdir(exist_ok=True)
        (trash / "deleted.mp4").write_bytes(b"video")
        (trash / "empty.mp4").touch()
    for hidden in (False, True):
        job = scan(client, [workspace], include_hidden=hidden)
        assert job["status"] == "completed", job
        assert job["discovered"] == 2
        groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
        assert len(groups) == 1
        assert groups[0]["member_count"] == 2
    job = scan(client, [workspace / "$RECYCLE.BIN"], include_hidden=True)
    assert job["discovered"] == 0


def test_thumbnail_available_for_active_file_before_analysis_is_ready(client, workspace, monkeypatch):
    from threading import Event
    from PIL import Image
    from app.database.models import File

    Image.new("RGB", (80, 60), "green").save(workspace / "processing.png")
    manager = client.app.state.manager
    original = manager.process_file
    entered, release = Event(), Event()
    selected = []
    def controlled(scan_id, file_id, checkpoint):
        with manager.sessions() as session:
            file = session.get(File, file_id)
            path = file.path
        selected.append(file_id)
        manager.update_activity(scan_id, file_id, path=path, phase="metadata", size=1,
                                bytes_done=0, frames_done=0, frames_total=0)
        entered.set()
        assert release.wait(5)
        return original(scan_id, file_id, checkpoint)
    monkeypatch.setattr(manager, "process_file", controlled)
    job = client.post("/api/v1/scans", json={"roots": [str(workspace)]}).json()
    try:
        assert entered.wait(5)
        file_id = selected[0]
        assert client.get(f"/api/v1/files/{file_id}").json()["status"] == "discovered"
        activity = client.get(f"/api/v1/scans/{job['id']}").json()["activity"]
        assert activity[0]["file_id"] == file_id
        url = f"/api/v1/files/{file_id}/thumbnail"
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "image/jpeg"
        manager.clear_activity(job["id"], file_id)
        assert client.get(url).status_code == 404
    finally:
        release.set()
        manager.active.result(timeout=5)
