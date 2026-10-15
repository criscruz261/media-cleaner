import copy
import subprocess
import pytest
from PIL import ImageDraw
from app.core.media_tools import executable, run_media
from app.hashing.sha256 import ScanStopped
from app.similarity.temporal import compare_sequences, fingerprint_animation
from app.similarity.sequences import SequenceIndex
from conftest import scan
from test_similarity import sample

TOOLS = bool(executable("ffmpeg") and executable("ffprobe"))


def make_frames(directory, seed=19):
    directory.mkdir()
    for index in range(24):
        path = directory / f"frame{index:03d}.png"
        image = sample(path, seed=seed)
        draw = ImageDraw.Draw(image)
        draw.rectangle((index * 5, 30, index * 5 + 35, 70), fill=(250, 50, 70))
        draw.ellipse((130, index * 3, 165, index * 3 + 35), fill=(20, 230, 120))
        image.save(path)


def make_video(path, frames, codec="libx264", scale="240:160", rate="8", sound="440"):
    command = [
        executable("ffmpeg"),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-threads",
        "1",
        "-filter_threads",
        "1",
        "-framerate",
        "8",
        "-i",
        str(frames / "frame%03d.png"),
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={sound}:sample_rate=22050",
        "-vf",
        f"scale={scale}",
        "-r",
        rate,
        "-c:v",
        codec,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    subprocess.run(command, capture_output=True, check=True, timeout=30)


@pytest.mark.skipif(not TOOLS, reason="Install FFmpeg and FFprobe for real codec integration tests")
def test_real_video_transcoding_framerate_and_manual_cleanup(client, workspace):
    frames = workspace.parent / "source-frames"
    make_frames(frames)
    make_video(workspace / "original.MOV", frames)
    make_video(workspace / "reencoded.mp4", frames, codec="mpeg4", scale="120:80", rate="16", sound="880")
    other = workspace.parent / "other-frames"
    make_frames(other, seed=273)
    make_video(workspace / "unrelated.mp4", other)
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    temporal = [group for group in groups if group["evidence"].get("media_kind") == "sequence"]
    assert len(temporal) == 1, groups
    group = temporal[0]
    detail = client.get("/api/v1/groups/" + group["id"]).json()
    assert {file["name"] for file in detail["files"]} == {"original.MOV", "reencoded.mp4"}
    assert all(file["keep"] for file in detail["files"])
    assert group["evidence"]["minimum_matched_samples"] >= 6
    selected = next(file for file in detail["files"] if file["name"] == "reencoded.mp4")
    client.post("/api/v1/groups/" + group["id"] + "/review", json={"changes": {selected["id"]: False}})
    plan = client.post(
        "/api/v1/cleanup/plan",
        json={"group_id": group["id"], "file_ids": [selected["id"]], "destination": "quarantine"},
    )
    assert plan.status_code == 201, plan.text
    value = plan.json()
    outcome = client.post(
        "/api/v1/cleanup/execute", json={"plan_id": value["id"], "token": value["token"], "confirmed": True}
    )
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["status"] == "completed"
    assert (workspace / "original.MOV").exists()
    assert not (workspace / "reencoded.mp4").exists()
    assert (
        client.post("/api/v1/cleanup/" + value["id"] + "/restore", json={"confirmed": True}).json()["status"]
        == "restored"
    )


@pytest.mark.skipif(not TOOLS, reason="FFmpeg/FFprobe required")
def test_sequence_cache_and_cancellation(client, workspace, monkeypatch):
    frames = workspace.parent / "frames"
    make_frames(frames)
    make_video(workspace / "clip.mp4", frames)
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed"

    def should_not_decode(*_args):
        pytest.fail("An unchanged cached clip was decoded again")

    monkeypatch.setattr("app.similarity.temporal.fingerprint_video", should_not_decode)
    assert scan(client, [workspace], mode="similar")["status"] == "completed"
    calls = []

    def checkpoint():
        calls.append(True)
        if len(calls) > 1:
            raise ScanStopped()

    with pytest.raises(ScanStopped):
        run_media([executable("ffmpeg"), "-version"], checkpoint)


def descriptor(values, duration=10):
    return {
        "duration": duration,
        "kind": "video",
        "frames": [
            {
                "slot": slot,
                "phash": f"{value:016x}",
                "dhash": f"{value:016x}",
                "aspect": 1.5,
                "color": [50, 70, 100],
            }
            for slot, value in enumerate(values)
        ],
    }


def test_sequence_duration_order_and_shared_intro():
    original = descriptor([index * 12345 for index in range(9)])
    assert compare_sequences(original, copy.deepcopy(original), "balanced")
    assert compare_sequences(original, {**original, "duration": 20}, "balanced") is None
    reversed_clip = copy.deepcopy(original)
    values = list(reversed_clip["frames"])
    reversed_clip["frames"] = [{**frame, "slot": slot} for slot, frame in enumerate(reversed(values))]
    assert compare_sequences(original, reversed_clip, "balanced") is None
    intro = descriptor([index * 12345 if index < 2 else (1 << 63) - index * 978 for index in range(9)])
    assert compare_sequences(original, intro, "balanced") is None
    still = descriptor([12345] * 9)
    assert compare_sequences(still, still, "balanced") is None


def test_sequence_index_includes_qualifying_duration_neighbors():
    index = SequenceIndex()
    original = descriptor([index * 12345 for index in range(9)], duration=10)
    index.add(original, "original")
    index.add({**original, "duration": 20}, "different-duration")
    assert index.candidates({**original, "duration": 10.2}, "balanced") == ["original"]


def test_animated_gif_and_webp_sequence_similarity_and_preview(client, workspace):
    frames = []
    for index in range(9):
        frames.append(sample(workspace.parent / f"animation-frame{index}.png", seed=19 + index))
    frames[0].save(workspace / "animation.gif", save_all=True, append_images=frames[1:], duration=120, loop=0)
    frames[0].save(
        workspace / "animation.webp",
        save_all=True,
        append_images=frames[1:],
        duration=120,
        loop=0,
        lossless=True,
    )
    left = fingerprint_animation(workspace / "animation.gif")
    right = fingerprint_animation(workspace / "animation.webp")
    assert compare_sequences(left, right, "balanced")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    assert len(groups) == 1, groups
    assert groups[0]["evidence"]["member_kinds"] == ["animation"]
    files = client.get("/api/v1/groups/" + groups[0]["id"]).json()["files"]
    response = client.get("/api/v1/files/" + files[0]["id"] + "/preview")
    assert response.headers["content-type"] in {"image/gif", "image/webp"}


def test_missing_tools_and_corrupt_media_are_reported(client, workspace, monkeypatch):
    (workspace / "broken.MOV").write_bytes(b"not a video")
    monkeypatch.setattr("app.similarity.temporal.executable", lambda _name: None)
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    warnings = client.get("/api/v1/scans/" + job["id"] + "/warnings").json()
    assert warnings["total"] == 1
    assert any("FFprobe is missing" in warning for warning in warnings["items"][0]["warnings"])
    assert client.get("/api/v1/groups?scan_id=" + job["id"]).json()["total"] == 0


@pytest.mark.skipif(not TOOLS, reason="FFmpeg/FFprobe required")
def test_gif_to_mp4_similarity(client, workspace):
    frames = [sample(workspace.parent / f"cross-frame{index}.png", seed=19 + index) for index in range(9)]
    frames[0].save(workspace / "animated.gif", save_all=True, append_images=frames[1:], duration=120, loop=0)
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-i",
            str(workspace / "animated.gif"),
            "-vf",
            "scale=120:80",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(workspace / "export.mp4"),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    assert len(groups) == 1, groups
    assert groups[0]["evidence"]["member_kinds"] == ["animation", "video"]


@pytest.mark.skipif(not TOOLS, reason="FFmpeg/FFprobe required")
def test_mkv_container_and_video_decode_failure(client, workspace):
    frames = workspace.parent / "mkv-frames"
    make_frames(frames)
    make_video(workspace / "clip.MOV", frames)
    subprocess.run(
        [
            executable("ffmpeg"),
            "-v",
            "error",
            "-y",
            "-i",
            str(workspace / "clip.MOV"),
            "-c",
            "copy",
            str(workspace / "remuxed.mkv"),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    (workspace / "corrupt.insv").write_bytes(b"unsupported container")
    job = scan(client, [workspace], mode="similar")
    assert job["status"] == "completed", job
    groups = client.get("/api/v1/groups?scan_id=" + job["id"]).json()["items"]
    assert len(groups) == 1, groups
    assert groups[0]["evidence"]["member_kinds"] == ["video"]
    warnings = client.get("/api/v1/scans/" + job["id"] + "/warnings").json()
    assert any("corrupt.insv" in item["path"] for item in warnings["items"])
