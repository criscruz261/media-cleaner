from conftest import duplicate_group
from app.database.models import FileReviewChoice


def test_clear_scan_selections_requires_confirmation_and_persists(client, workspace):
    group = duplicate_group(client, workspace)
    scan_id = group["scan_id"]
    endpoint = f"/api/v1/scans/{scan_id}/clear-deletion-selections"
    assert any(not file["keep"] for file in group["files"])
    assert client.post(endpoint, json={"confirmed": False}).status_code == 400
    unchanged = client.get(f"/api/v1/groups/{group['id']}").json()
    assert any(not file["keep"] for file in unchanged["files"])
    assert client.post(endpoint, json={"confirmed": True}).status_code == 200
    updated = client.get(f"/api/v1/groups/{group['id']}").json()
    assert all(file["keep"] for file in updated["files"])
    assert updated["review_status"] == "reviewed"
    assert not updated["evidence"]["allow_keep_none"]
    with client.app.state.sessions() as session:
        for file in updated["files"]:
            assert session.get(FileReviewChoice, (file["id"], "EXACT_DUPLICATE")).keep
    assert all((workspace / file["name"]).exists() for file in updated["files"])
