import time
import pytest
from fastapi.testclient import TestClient
from app.api.main import create_app


@pytest.fixture
def workspace(tmp_path):
    media = (tmp_path / "media").resolve()
    media.mkdir()
    return media


@pytest.fixture
def client(tmp_path):
    app = create_app((tmp_path / "data").resolve(), token="test-token")
    with TestClient(
        app, base_url="http://127.0.0.1:8765", headers={"Authorization": "Bearer test-token"}
    ) as client:
        yield client


def scan(client, roots, **options):
    response = client.post("/api/v1/scans", json={"roots": [str(root) for root in roots], **options})
    assert response.status_code == 201, response.text
    scan_id = response.json()["id"]
    for _ in range(400):
        job = client.get(f"/api/v1/scans/{scan_id}").json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.01)
    pytest.fail("Scan worker did not finish")


def duplicate_group(client, media):
    (media / "IMG_0971.MOV").write_bytes(b"video original")
    (media / "IMG_0971 copy.MOV").write_bytes(b"video original")
    job = scan(client, [media])
    assert job["status"] == "completed", job
    group = client.get(f"/api/v1/groups?scan_id={job['id']}").json()["items"][0]
    return client.get("/api/v1/groups/" + group["id"]).json()
