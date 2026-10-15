from pathlib import Path
import numpy as np
import tifffile
from app.metadata.decoding import load_still
from conftest import scan


def synthetic_dng(path: Path):
    y, x = np.mgrid[:128, :192]
    pixels = ((x * 7 + y * 11 + (x // 12 % 2) * 700 + (y // 16 % 2) * 400) % 3500 + 200).astype(np.uint16)
    tags = [
        (50706, "B", 4, (1, 4, 0, 0), False),
        (50707, "B", 4, (1, 3, 0, 0), False),
        (50708, "s", 0, "Synthetic Test Camera", False),
        (33421, "H", 2, (2, 2), False),
        (33422, "B", 4, (0, 1, 1, 2), False),
        (50717, "I", 1, 4095, False),
        (50714, "H", 1, 0, False),
        (50778, "H", 1, 21, False),
        (50721, "2i", 9, (1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1), False),
        (50728, "2I", 3, (1, 1, 1, 1, 1, 1), False),
    ]
    tifffile.imwrite(path, pixels, photometric=32803, metadata=None, extratags=tags)


def test_raw_and_rendered_image_similarity_preview_and_protection(client, workspace):
    synthetic_dng(workspace / "camera.dng")
    image = load_still(workspace / "camera.dng")
    image.save(workspace / "render.png")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    assert len(groups) == 1, groups
    assert groups[0]["classification"] == "SIMILAR_CONTENT"
    files = client.get("/api/v1/groups/" + groups[0]["id"]).json()["files"]
    raw = next(file for file in files if file["name"] == "camera.dng")
    assert raw["protected_reason"]
    assert raw["metadata"]["format"] == "RAW"
    preview = client.get("/api/v1/files/" + raw["id"] + "/preview")
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "image/jpeg"
    assert (
        client.post(
            "/api/v1/groups/" + groups[0]["id"] + "/review", json={"changes": {raw["id"]: False}}
        ).status_code
        == 400
    )


def test_corrupt_raw_does_not_abort_other_media(client, workspace):
    (workspace / "bad.CR3").write_bytes(b"not a raw file")
    synthetic_dng(workspace / "valid.dng")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    warnings = client.get("/api/v1/scans/" + job["id"] + "/warnings").json()
    assert warnings["total"] == 1
    assert warnings["items"][0]["name"] == "bad.CR3"
