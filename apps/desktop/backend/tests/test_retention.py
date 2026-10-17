from types import SimpleNamespace
from app.retention.recommend import recommendation
from app.core.filesystem import protection


def file(name, protected=None):
    return SimpleNamespace(id=name, name=name, protected_reason=protected)


def test_original_filename_and_manual_ambiguity():
    assert recommendation([file("IMG_0971 copy.MOV"), file("IMG_0971.MOV")])[0] == "IMG_0971.MOV"
    assert recommendation([file("IMG_0971 (1).MOV"), file("IMG_0971.MOV")])[0] == "IMG_0971.MOV"
    assert recommendation([file("b.png"), file("a.png")])[0] == "a.png"
    assert recommendation([file("RAW.dng", "RAW original"), file("copy.dng")])[0] == "RAW.dng"


def test_raw_and_possible_live_photo_companions(workspace):
    (workspace / "IMG_1234.HEIC").write_bytes(b"photo")
    (workspace / "IMG_1234.MOV").write_bytes(b"video")
    assert "companion" in protection(workspace / "IMG_1234.HEIC", [])
    assert "companion" in protection(workspace / "IMG_1234.MOV", [])
    assert "RAW" in protection(workspace / "original.dng", [])


def test_saved_exact_groups_default_to_one_keeper_without_overwriting_review(client, workspace):
    from conftest import duplicate_group
    from sqlalchemy import select
    from app.database.models import DuplicateGroup, GroupMember
    from app.retention.recommend import initialize_exact_selections

    group = duplicate_group(client, workspace)
    with client.app.state.sessions.begin() as session:
        session.get(DuplicateGroup, group["id"]).recommended_id = None
        for member in session.scalars(select(GroupMember).where(GroupMember.group_id == group["id"])):
            member.keep = True
    initialize_exact_selections(client.app.state.sessions)
    detail = client.get("/api/v1/groups/" + group["id"]).json()
    assert [file["name"] for file in detail["files"] if file["keep"]] == ["IMG_0971.MOV"]
    # User choices, including keeping every copy, survive startup normalization.
    assert client.post("/api/v1/groups/" + group["id"] + "/review", json={
        "keep_ids": [file["id"] for file in detail["files"]],
    }).status_code == 200
    initialize_exact_selections(client.app.state.sessions)
    assert all(file["keep"] for file in client.get("/api/v1/groups/" + group["id"]).json()["files"])
