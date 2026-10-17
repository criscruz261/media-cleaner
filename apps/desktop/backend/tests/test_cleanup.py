from pathlib import Path
from conftest import duplicate_group


def plan(client, group, destination="quarantine"):
    ids = [file["id"] for file in group["files"] if not file["keep"]]
    response = client.post("/api/v1/cleanup/plan", json={"file_ids": ids, "destination": destination})
    assert response.status_code == 201, response.text
    return response.json()


def execute(client, value, confirmed=True):
    return client.post(
        "/api/v1/cleanup/execute",
        json={"plan_id": value["id"], "token": value["token"], "confirmed": confirmed},
    )


def test_plan_is_dry_run_confirmation_quarantine_and_restore(client, workspace):
    group = duplicate_group(client, workspace)
    value = plan(client, group)
    assert all(Path(file["path"]).exists() for file in group["files"])
    assert execute(client, value, confirmed=False).status_code == 400
    outcome = execute(client, value)
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["status"] == "completed"
    item = outcome.json()["items"][0]
    assert not Path(item["source"]).exists()
    assert Path(item["quarantine_path"]).read_bytes() == b"video original"
    assert Path(item["keeper"]).exists()
    assert execute(client, value).status_code == 400
    assert (
        client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": False}).status_code
        == 400
    )
    recovery = client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": True})
    assert recovery.status_code == 200, recovery.text
    assert recovery.json()["status"] == "restored"
    assert Path(item["source"]).read_bytes() == b"video original"


def test_changed_selected_or_missing_keeper_blocks_whole_plan(client, workspace):
    group = duplicate_group(client, workspace)
    value = plan(client, group)
    item = value["items"][0]
    Path(item["source"]).write_bytes(b"changed")
    assert execute(client, value).status_code == 400
    assert Path(item["source"]).exists()
    assert Path(item["keeper"]).exists()


def test_disconnected_or_missing_keeper(client, workspace):
    group = duplicate_group(client, workspace)
    value = plan(client, group)
    Path(value["items"][0]["keeper"]).unlink()
    assert execute(client, value).status_code == 409
    assert Path(value["items"][0]["source"]).exists()


def test_protected_directory_rejected(client, workspace):
    group = duplicate_group(client, workspace)
    assert client.put("/api/v1/settings", json={"protected_directories": [str(workspace)]}).status_code == 200
    response = client.post(
        "/api/v1/cleanup/plan",
        json={
            "file_ids": [file["id"] for file in group["files"] if not file["keep"]],
            "destination": "quarantine",
        },
    )
    assert response.status_code == 400
    assert all(Path(file["path"]).exists() for file in group["files"])


def test_trash_failure_never_falls_back_to_delete(client, workspace, monkeypatch):
    group = duplicate_group(client, workspace)
    value = plan(client, group, "trash")

    def fail(_path):
        raise PermissionError("Trash unavailable")

    monkeypatch.setattr("app.cleanup.service.send2trash", fail)
    response = execute(client, value)
    assert response.status_code == 200
    assert response.json()["status"] == "partial"
    assert all(Path(file["path"]).exists() for file in group["files"])


def test_restore_never_overwrites_file(client, workspace):
    group = duplicate_group(client, workspace)
    value = plan(client, group)
    result = execute(client, value).json()
    source = Path(result["items"][0]["source"])
    source.write_bytes(b"new file")
    recovery = client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": True}).json()
    assert recovery["status"] == "partial"
    assert source.read_bytes() == b"new file"
    assert Path(result["items"][0]["quarantine_path"]).exists()


def test_symlink_replacement_and_expired_plan_block_cleanup(client, workspace):
    from app.database.models import CleanupOperation

    group = duplicate_group(client, workspace)
    value = plan(client, group)
    with client.app.state.sessions.begin() as session:
        session.get(CleanupOperation, value["id"]).expires_at = "2000-01-01T00:00:00+00:00"
    assert execute(client, value).status_code == 400
    fresh = plan(client, group)
    source = Path(fresh["items"][0]["source"])
    source.unlink()
    source.symlink_to(fresh["items"][0]["keeper"])
    assert execute(client, fresh).status_code == 400
    assert Path(fresh["items"][0]["keeper"]).exists()


def test_quarantine_symlink_is_rejected(client, workspace):
    group = duplicate_group(client, workspace)
    elsewhere = workspace.parent / "elsewhere"
    elsewhere.mkdir()
    (workspace / ".media-cleaner-quarantine").symlink_to(elsewhere, target_is_directory=True)
    value = plan(client, group)
    response = execute(client, value)
    assert response.json()["status"] == "partial"
    assert all(Path(file["path"]).exists() for file in group["files"])
    assert not list(elsewhere.iterdir())


def test_batch_cleanup_across_exact_groups_remains_supported(client, workspace):
    from conftest import scan

    for name, content in [
        ("a.MOV", b"first"),
        ("a copy.MOV", b"first"),
        ("b.MOV", b"second"),
        ("b copy.MOV", b"second"),
    ]:
        (workspace / name).write_bytes(content)
    job = scan(client, [workspace])
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    ids = []
    for group in groups:
        detail = client.get("/api/v1/groups/" + group["id"]).json()
        ids.extend(file["id"] for file in detail["files"] if not file["keep"])
    response = client.post("/api/v1/cleanup/plan", json={"file_ids": ids, "destination": "quarantine"})
    assert response.status_code == 201, response.text
    outcome = execute(client, response.json())
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["status"] == "completed", outcome.json()
    assert (workspace / "a.MOV").exists() and (workspace / "b.MOV").exists()


def test_keep_none_requires_group_review_confirmation_and_can_restore(client, workspace):
    group = duplicate_group(client, workspace)
    review = client.post("/api/v1/groups/" + group["id"] + "/review", json={"keep_ids": []})
    assert review.status_code == 200, review.text
    ids = [file["id"] for file in group["files"]]
    payload = {"file_ids": ids, "destination": "quarantine"}
    assert client.post("/api/v1/cleanup/plan", json=payload).status_code == 400
    response = client.post("/api/v1/cleanup/plan", json={**payload, "group_id": group["id"]})
    assert response.status_code == 201, response.text
    value = response.json()
    assert all(item["keeper"] is None for item in value["items"])
    assert execute(client, value, confirmed=False).status_code == 400
    assert all(Path(file["path"]).exists() for file in group["files"])
    result = execute(client, value)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "completed", result.text
    assert all(not Path(file["path"]).exists() for file in group["files"])
    restored = client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": True})
    assert restored.json()["status"] == "restored"
    assert all(Path(file["path"]).exists() for file in group["files"])


def test_keep_none_preview_invalidated_when_choices_change(client, workspace):
    group = duplicate_group(client, workspace)
    client.post("/api/v1/groups/" + group["id"] + "/review", json={"keep_ids": []})
    value = client.post(
        "/api/v1/cleanup/plan",
        json={
            "file_ids": [file["id"] for file in group["files"]],
            "destination": "quarantine",
            "group_id": group["id"],
        },
    ).json()
    client.post("/api/v1/groups/" + group["id"] + "/review", json={"keep_ids": [group["files"][0]["id"]]})
    assert execute(client, value).status_code == 400
    assert all(Path(file["path"]).exists() for file in group["files"])


def test_selected_batch_across_exact_similar_and_keep_none(client, workspace):
    from conftest import scan
    from app.database.models import DuplicateGroup

    for name, content in [
        ("a.MOV", b"first"),
        ("a copy.MOV", b"first"),
        ("b.MOV", b"second"),
        ("b copy.MOV", b"second"),
        ("c.MOV", b"untouched"),
        ("c copy.MOV", b"untouched"),
    ]:
        (workspace / name).write_bytes(content)
    job = scan(client, [workspace])
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    reviewed = groups[:2]
    with client.app.state.sessions.begin() as session:
        session.get(DuplicateGroup, reviewed[1]["id"]).classification = "SIMILAR_CONTENT"
    expected = []
    for group in reviewed:
        detail = client.get("/api/v1/groups/" + group["id"]).json()
        expected.extend(file["path"] for file in detail["files"])
        assert (
            client.post("/api/v1/groups/" + group["id"] + "/review", json={"keep_ids": []}).status_code == 200
        )
    response = client.post(
        "/api/v1/cleanup/plan-selected", json={"scan_id": job["id"], "destination": "quarantine"}
    )
    assert response.status_code == 201, response.text
    value = response.json()
    assert {item["source"] for item in value["items"]} == set(expected)
    assert len(value["items"]) == 4
    assert execute(client, value, confirmed=False).status_code == 400
    assert all(Path(path).exists() for path in expected)
    result = execute(client, value)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "completed", result.text
    assert all(not Path(path).exists() for path in expected)
    restored = client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": True})
    assert restored.json()["status"] == "restored"
    assert all(Path(path).exists() for path in expected)


def test_selected_batch_excludes_unreviewed_groups(client, workspace):
    group = duplicate_group(client, workspace)
    response = client.post("/api/v1/cleanup/plan-selected", json={"scan_id": group["scan_id"]})
    assert response.status_code == 400
    assert all(Path(file["path"]).exists() for file in group["files"])
