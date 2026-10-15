from fastapi.testclient import TestClient
from app.api.main import create_app
from conftest import scan
from test_similarity import sample


def test_folder_cache_rebuilds_analysis_and_choices_with_a_fresh_app_database(
    client, workspace, tmp_path, monkeypatch
):
    sample(workspace / "original.png")
    (workspace / "copy.png").write_bytes((workspace / "original.png").read_bytes())
    first = scan(client, [workspace], mode="similar")
    groups = client.get(f"/api/v1/scans/{first['id']}/matches").json()["items"]
    files = client.get(f"/api/v1/groups/{groups[0]['id']}").json()["files"]
    copy = next(file for file in files if file["name"] == "copy.png")
    assert (
        client.post(
            f"/api/v1/groups/{groups[0]['id']}/review", json={"changes": {copy["id"]: False}}
        ).status_code
        == 200
    )
    assert len(list((workspace / ".media-cleaner-cache").glob("*/*.json"))) == 2

    assert scan(client, [workspace], mode="exact")["errors"] == 0

    def unexpected(*args, **kwargs):
        raise AssertionError("Unchanged media should reuse the folder checkpoint")

    monkeypatch.setattr("app.workers.manager.hash_file", unexpected)
    monkeypatch.setattr("app.workers.manager.extract", unexpected)
    monkeypatch.setattr("app.workers.manager.fingerprint_image", unexpected)
    with TestClient(
        create_app(tmp_path / "fresh-app-data", token="new"),
        base_url="http://127.0.0.1:8765",
        headers={"Authorization": "Bearer new"},
    ) as fresh:
        second = scan(fresh, [workspace], mode="similar", include_hidden=True)
        assert second["status"] == "completed", second
        assert second["errors"] == 0
        assert second["discovered"] == 2
        assert second["cache_hits"] == 2
        groups = fresh.get(f"/api/v1/scans/{second['id']}/matches").json()["items"]
        files = fresh.get(f"/api/v1/groups/{groups[0]['id']}").json()["files"]
        assert not next(file for file in files if file["name"] == "copy.png")["keep"]
        assert next(file for file in files if file["name"] == "original.png")["keep"]


def test_changed_file_and_corrupt_checkpoint_are_not_reused(client, workspace, tmp_path):
    from app.core.filesystem import identity
    from app.scanner import folder_cache

    path = workspace / "photo.png"
    sample(path)
    job = scan(client, [workspace], mode="similar")
    assert job["errors"] == 0
    key = identity(path).key(str(path))
    assert folder_cache.read(path, [str(workspace)], key)
    entry = folder_cache.location(path, [str(workspace)], key)
    entry.write_text("{broken")
    assert folder_cache.read(path, [str(workspace)], key) is None
    job = scan(client, [workspace], mode="similar")
    assert job["errors"] == 0
    assert folder_cache.read(path, [str(workspace)], key)
    sample(path, seed=73)
    assert folder_cache.read(path, [str(workspace)], identity(path).key(str(path))) is None


def test_symlink_cache_is_skipped_and_cannot_write_outside_root(client, workspace, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / ".media-cleaner-cache").symlink_to(outside, target_is_directory=True)
    sample(workspace / "photo.png")
    job = scan(client, [workspace], mode="similar", include_hidden=True)
    assert job["status"] == "completed"
    assert job["errors"] == 0
    assert job["discovered"] == 1
    assert list(outside.iterdir()) == []
    warnings = client.get(f"/api/v1/scans/{job['id']}/warnings").json()["items"]
    assert any("Folder cache unavailable" in warning for file in warnings for warning in file["warnings"])
