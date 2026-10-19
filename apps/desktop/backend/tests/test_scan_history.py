from conftest import scan
from app.database.models import ScanJob


def test_history_favorites_and_atomic_delete_preserve_cache(client, workspace):
    (workspace / "a.jpg").write_bytes(b"saved media")
    first = scan(client, [workspace])
    second = scan(client, [workspace])
    a, b = first["id"], second["id"]
    assert client.post(f"/api/v1/scans/{a}/favorite", json={"favorite": True}).json()["favorite"]
    response = client.post("/api/v1/scans/history/delete", json={"scan_ids": [a, b], "confirmed": True})
    assert response.status_code == 400
    assert client.get("/api/v1/scans").json()["total"] == 2
    assert client.post("/api/v1/scans/history/delete", json={"scan_ids": [b]}).status_code == 400
    assert client.post("/api/v1/scans/history/delete", json={"scan_ids": [b], "confirmed": True}).status_code == 200
    history = client.get("/api/v1/scans?limit=1").json()
    assert history["total"] == 1
    assert history["items"][0]["id"] == a
    assert history["items"][0]["favorite"]
    assert (workspace / "a.jpg").read_bytes() == b"saved media"
    assert list((workspace / ".media-cleaner-cache").rglob("*.json"))
    assert client.post(f"/api/v1/scans/{a}/favorite", json={"favorite": False}).status_code == 200
    assert client.post("/api/v1/scans/history/delete", json={"scan_ids": [a], "confirmed": True}).status_code == 200
    assert client.get("/api/v1/scans").json()["total"] == 0


def test_active_history_cannot_be_deleted(client):
    with client.app.state.sessions.begin() as session:
        job = ScanJob(options={"roots": []}, status="running")
        session.add(job)
        session.flush()
        scan_id = job.id
    assert client.post("/api/v1/scans/history/delete", json={"scan_ids": [scan_id], "confirmed": True}).status_code == 400
    assert client.get("/api/v1/scans").json()["total"] == 1
