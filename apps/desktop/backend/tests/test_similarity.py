import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageOps
from sqlalchemy import select
from app.database.models import Fingerprint
from app.similarity.images import fingerprint_image, HashIndex, Signature
from conftest import scan


def sample(path: Path, seed=7):
    randomizer = random.Random(seed)
    image = Image.new("RGB", (240, 160), (75, 120, 165))
    draw = ImageDraw.Draw(image)
    for _ in range(35):
        x, y = randomizer.randrange(220), randomizer.randrange(140)
        color = tuple(randomizer.randrange(256) for _ in range(3))
        draw.rectangle((x, y, x + 20, y + 20), fill=color)
    image.save(path)
    return image


def test_cross_format_resized_brightness_and_unrelated(client, workspace):
    image = sample(workspace / "original.png")
    image.resize((120, 80)).save(workspace / "resized.jpg", quality=88)
    ImageEnhance.Brightness(image).enhance(1.07).save(workspace / "bright.webp", quality=90)
    sample(workspace / "unrelated.png", seed=124)
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
    similar = [group for group in groups if group["classification"] == "SIMILAR_CONTENT"]
    assert len(similar) == 1, groups
    assert similar[0]["member_count"] == 3
    assert similar[0]["evidence"]["algorithm"] == "imagehash-phash-dhash"
    details = client.get("/api/v1/groups/" + similar[0]["id"]).json()
    assert {file["name"] for file in details["files"]} == {"original.png", "resized.jpg", "bright.webp"}
    assert all(file["keep"] for file in details["files"])
    assert details["recommended_id"] is None


def test_orientation_normalization(workspace):
    image = sample(workspace / "normal.png")
    rotated = image.transpose(Image.Transpose.ROTATE_90)
    exif = Image.Exif()
    exif[274] = 6
    rotated.save(workspace / "oriented.png", exif=exif)
    normal, oriented = (
        fingerprint_image(workspace / "normal.png"),
        fingerprint_image(workspace / "oriented.png"),
    )
    assert normal["phash"] == oriented["phash"]
    assert normal["dhash"] == oriented["dhash"]


def test_flat_animated_and_corrupt_files_do_not_become_visual_duplicates(client, workspace):
    Image.new("RGB", (100, 100), "red").save(workspace / "red.png")
    Image.new("RGB", (100, 100), "blue").save(workspace / "blue.jpg")
    a = sample(workspace / "source.png")
    b = ImageOps.mirror(a)
    a.save(workspace / "animation.gif", save_all=True, append_images=[b], duration=100, loop=0)
    (workspace / "corrupt.jpg").write_bytes(b"not an image")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed"
    groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
    assert not [group for group in groups if group["classification"] == "SIMILAR_CONTENT"]
    files = client.get(f"/api/v1/files?scan_id={job['id']}").json()["items"]
    for file in files:
        if file["name"] not in {"source.png", "animation.gif"}:
            assert client.get("/api/v1/files/" + file["id"]).json()["warnings"]


def test_fingerprints_cached_and_invalidated(client, workspace, monkeypatch):
    sample(workspace / "original.png")
    first = scan(client, [workspace], mode="similar")
    assert first["status"] == "completed"
    import app.workers.manager as manager

    original = manager.fingerprint_image
    calls = []

    def counted(path):
        calls.append(str(path))
        return original(path)

    monkeypatch.setattr(manager, "fingerprint_image", counted)
    second = scan(client, [workspace], mode="similar")
    assert second["status"] == "completed"
    assert calls == []
    sample(workspace / "original.png", seed=12)
    third = scan(client, [workspace], mode="similar")
    assert third["status"] == "completed"
    assert len(calls) == 1
    with client.app.state.sessions() as session:
        fingerprints = session.scalars(select(Fingerprint)).all()
        assert len(fingerprints) == 3
        assert all(item.algorithm == "imagehash-phash-dhash" and item.version == "3" for item in fingerprints)


def test_index_matches_exhaustive_hamming_search():
    randomizer = random.Random(17)
    values = [randomizer.getrandbits(64) for _ in range(150)] + [0, 1, 3, 7, 15]
    index = HashIndex()
    for number, value in enumerate(values):
        index.add(value, str(number))
    for value in values[::10] + [0, 1, 7]:
        expected = {
            str(number) for number, candidate in enumerate(values) if (value ^ candidate).bit_count() <= 8
        }
        assert set(index.search(value, 8)) == expected


def test_complete_link_avoids_similarity_chains():
    a = Signature(0, 0, 1, (50, 50, 50))
    b = Signature(15, 15, 1, (50, 50, 50))
    c = Signature(255, 255, 1, (50, 50, 50))
    assert a.compatible(b, (4, 6))
    assert b.compatible(c, (4, 6))
    assert not all(c.compatible(other, (4, 6)) for other in [a, b])


def test_manual_similar_photo_quarantine_keeps_different_content(client, workspace):
    image = sample(workspace / "original.png")
    image.resize((120, 80)).save(workspace / "resized.jpg", quality=90)
    job = scan(client, [workspace], mode="similar")
    groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
    group = next(group for group in groups if group["classification"] == "SIMILAR_CONTENT")
    files = client.get("/api/v1/groups/" + group["id"]).json()["files"]
    selected = next(file for file in files if file["name"] == "resized.jpg")
    payload = {"file_ids": [selected["id"]], "destination": "quarantine", "group_id": group["id"]}
    assert client.post("/api/v1/cleanup/plan", json=payload).status_code == 400
    assert (
        client.post(
            "/api/v1/groups/" + group["id"] + "/review", json={"changes": {selected["id"]: False}}
        ).status_code
        == 200
    )
    assert client.post("/api/v1/cleanup/plan", json={**payload, "group_id": None}).status_code == 400
    response = client.post("/api/v1/cleanup/plan", json=payload)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["items"][0]["classification"] == "SIMILAR_CONTENT"
    response = client.post(
        "/api/v1/cleanup/execute", json={"plan_id": plan["id"], "token": plan["token"], "confirmed": True}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed", response.json()
    assert (workspace / "original.png").exists()
    assert not (workspace / "resized.jpg").exists()


def test_invalid_sensitivity_rejected(client, workspace):
    assert (
        client.post(
            "/api/v1/scans", json={"roots": [str(workspace)], "mode": "similar", "sensitivity": "anything"}
        ).status_code
        == 422
    )


def test_real_group_builder_does_not_merge_weak_chains(client, workspace):
    from app.similarity.images import build_similar_groups, ALGORITHM, VERSION
    from app.database.models import File, DuplicateGroup
    from hashlib import sha256

    for name, value in [("a.png", b"a"), ("b.png", b"bb"), ("c.png", b"ccc")]:
        (workspace / name).write_bytes(value)
    job = scan(client, [workspace])
    with client.app.state.sessions() as session:
        files = session.scalars(select(File).where(File.scan_id == job["id"]).order_by(File.name)).all()
        for file, value in zip(files, [0, 15, 255]):
            file.sha256 = sha256(Path(file.path).read_bytes()).hexdigest()
            session.add(
                Fingerprint(
                    file_id=file.id,
                    algorithm=ALGORITHM,
                    version=VERSION,
                    value={
                        "phash": f"{value:016x}",
                        "dhash": f"{value:016x}",
                        "aspect": 1,
                        "color": [50, 50, 50],
                    },
                )
            )
        session.commit()
        build_similar_groups(session, job["id"], "strict", lambda: None)
        groups = session.scalars(select(DuplicateGroup).where(DuplicateGroup.scan_id == job["id"])).all()
        assert len(groups) == 1
        assert groups[0].member_count == 2
        assert groups[0].evidence["max_phash_distance"] == 4


def test_similar_mode_retains_exact_video_support(client, workspace):
    (workspace / "clip.MOV").write_bytes(b"video")
    (workspace / "clip copy.MOV").write_bytes(b"video")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed"
    groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
    assert len(groups) == 1
    assert groups[0]["classification"] == "EXACT_DUPLICATE"


def test_dashboard_does_not_count_similar_as_exact_or_double_savings(client, workspace):
    image = sample(workspace / "original.png")
    (workspace / "original copy.png").write_bytes((workspace / "original.png").read_bytes())
    image.resize((120, 80)).save(workspace / "resized.jpg", quality=90)
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed"
    stats = client.get("/api/v1/dashboard").json()
    assert stats["groups"] == 1
    assert stats["similar_groups"] == 1
    assert stats["recoverable"] == (workspace / "original.png").stat().st_size


def test_existing_phase1_database_is_upgraded_without_losing_history(tmp_path):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, MetaData, Table
    from app.database.models import now
    from uuid import uuid4
    from app.api.main import create_app
    from fastapi.testclient import TestClient

    data = (tmp_path / "old-data").resolve()
    data.mkdir()
    engine = create_engine("sqlite:///" + str(data / "media-cleaner.sqlite3"))
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
    old_id = str(uuid4())
    legacy = Table("scan_jobs", MetaData(), autoload_with=engine)
    with engine.begin() as connection:
        connection.execute(
            legacy.insert().values(
                id=old_id,
                options={"roots": []},
                status="completed",
                stage="complete",
                discovered=0,
                processed=0,
                bytes_processed=0,
                cache_hits=0,
                errors=0,
                created_at=now(),
                updated_at=now(),
            )
        )
    engine.dispose()
    application = create_app(data, token="test")
    with TestClient(
        application, base_url="http://127.0.0.1:8765", headers={"Authorization": "Bearer test"}
    ) as client:
        assert client.get("/api/v1/scans/" + old_id).json()["status"] == "completed"
        with application.state.sessions() as session:
            assert "cache_key" in {
                column["name"] for column in inspect(session.bind).get_columns("fingerprints")
            }


def test_scan_from_scratch_bypasses_database_and_folder_analysis(client, workspace, monkeypatch):
    import app.workers.manager as manager

    sample(workspace / "original.png")
    first = scan(client, [workspace], mode="similar")
    assert first["status"] == "completed"
    assert list((workspace / ".media-cleaner-cache").glob("*/*.json"))
    cached = scan(client, [workspace], mode="similar")
    assert cached["cache_hits"] == 1
    hashes, fingerprints = [], []
    original_hash, original_fingerprint = manager.hash_file, manager.fingerprint_image

    def hash_again(path, *args):
        hashes.append(path)
        return original_hash(path, *args)

    def fingerprint_again(path):
        fingerprints.append(path)
        return original_fingerprint(path)

    def no_folder_read(*args):
        raise AssertionError("A from-scratch scan must not read folder cache analysis")

    monkeypatch.setattr(manager, "hash_file", hash_again)
    monkeypatch.setattr(manager, "fingerprint_image", fingerprint_again)
    original_read = manager.folder_cache.read
    monkeypatch.setattr(manager.folder_cache, "read", no_folder_read)
    # Cache writing merges prior review choices; isolate analysis reads here.
    monkeypatch.setattr(manager.folder_cache, "write", lambda *args, **kwargs: None)
    fresh = scan(client, [workspace], mode="similar", force_rescan=True)
    assert fresh["status"] == "completed"
    assert fresh["cache_hits"] == 0
    assert len(hashes) == len(fingerprints) == 1

    # Resuming this fresh scan may still reuse its own completed checkpoints.
    monkeypatch.setattr(manager.folder_cache, "read", original_read)
    file_id = client.get(f"/api/v1/files?scan_id={fresh['id']}").json()["items"][0]["id"]
    client.app.state.manager.process_file(fresh["id"], file_id, lambda: None)
    assert len(hashes) == len(fingerprints) == 1


def test_added_loose_levels_progressively_widen_matching():
    from app.api.schemas import ScanRequest
    from app.similarity.images import PRESETS
    from app.similarity.temporal import MATCH_RATIO, DURATION_TOLERANCE

    original = Signature(0, 0, 1.5, (100, 100, 100))
    levels = ["broad", "very_loose", "extra_loose", "maximum"]
    for previous, current, bits in zip(levels, levels[1:], [14, 18, 22]):
        changed = Signature((1 << bits) - 1, 0, 1.5, (100, 100, 100))
        assert not original.compatible(changed, PRESETS[previous])
        assert original.compatible(changed, PRESETS[current])
        assert MATCH_RATIO[current] < MATCH_RATIO[previous]
        assert DURATION_TOLERANCE[current] > DURATION_TOLERANCE[previous]
        assert ScanRequest(roots=["/photos"], sensitivity=current).sensitivity == current


def test_maximum_recovers_viewpoint_and_missing_objects(client, workspace):
    from app.similarity.images import PRESETS

    atlas = Image.open(Path(__file__).parents[2] / "frontend/public/matching/sensitivity-atlas.png").convert(
        "RGB"
    )
    original = atlas.crop((0, 0, atlas.width // 2, atlas.height // 2))
    original.save(workspace / "original.png")
    viewpoint = original.transform(original.size, Image.Transform.AFFINE, (0.9, 0.08, 15, 0.02, 0.95, 5))
    viewpoint.save(workspace / "viewpoint.png")
    missing = original.copy()
    ImageDraw.Draw(missing).rectangle((25, 375, 320, 575), fill=(85, 100, 115))
    missing.save(workspace / "missing-object.png")
    a = Signature.from_value(fingerprint_image(workspace / "original.png"))
    for filename in ["viewpoint.png", "missing-object.png"]:
        b = Signature.from_value(fingerprint_image(workspace / filename))
        assert not a.compatible(b, PRESETS["strict"])
        assert a.compatible(b, PRESETS["maximum"])
    # Exercise indexed candidate lookup, not only the pairwise comparison.
    job = scan(client, [workspace], mode="similar", sensitivity="maximum")
    assert job["status"] == "completed"
    groups = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"]
    detail = [
        client.get("/api/v1/groups/" + group["id"]).json()
        for group in groups
        if group["classification"] == "SIMILAR_CONTENT"
    ]
    assert any(
        {file["name"] for file in group["files"]} >= {"original.png", "missing-object.png"}
        for group in detail
    )


def test_subject_index_finds_changed_hashes_and_filters_by_sensitivity():
    from app.similarity import subjects
    import numpy as np

    a = np.array([127, 0, 0, 0], dtype=np.int8).tobytes()
    b = np.array([100, 70, 0, 0], dtype=np.int8).tobytes()
    index = subjects.SubjectIndex()
    index.add(a, "subject")
    assert "subject" in list(index.search(b, 0.80))
    assert "subject" not in list(index.search(b, 0.98))
    original = Signature(0, 0, 1.5, (0, 0, 0), a)
    changed = Signature((1 << 64) - 1, (1 << 64) - 1, 2.5, (255, 255, 255), b)
    from app.similarity.images import PRESETS

    assert original.compatible(changed, PRESETS["maximum"])
    assert not original.compatible(changed, PRESETS["extra_loose"])


def test_current_sensitivity_photo_examples_qualify_at_selected_levels():
    from app.similarity.images import describe_image, PRESETS

    atlas = Image.open(Path(__file__).parents[2] / "frontend/public/matching/sensitivity-scenes.png").convert(
        "RGB"
    )
    width, height = atlas.width // 2, atlas.height // 4
    original = Signature.from_value(describe_image(atlas.crop((0, 0, width, height))))
    for cell, sensitivity in enumerate(
        ["strict", "balanced", "broad", "very_loose", "extra_loose", "maximum"], 1
    ):
        photo = atlas.crop(
            (cell % 2 * width, cell // 2 * height, (cell % 2 + 1) * width, (cell // 2 + 1) * height)
        )
        example = Signature.from_value(describe_image(photo))
        assert original.compatible(example, PRESETS[sensitivity]), sensitivity
