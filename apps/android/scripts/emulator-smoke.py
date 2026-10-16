"""Synthetic-only native Android smoke test. Refuses real devices or other AVDs."""

import json
import os
import random
import re
import sqlite3
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from app.core.media_tools import executable
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
TOOLS = ROOT / ".tools/android"
ADB = TOOLS / "sdk/platform-tools/adb"
ENV = {**os.environ, "ANDROID_USER_HOME": str(TOOLS / "user")}
PACKAGE = "com.photofold.mediacleaner"
ARTIFACTS = TOOLS / "smoke"
ARTIFACTS.mkdir(exist_ok=True)


def adb(*args, binary=False):
    result = subprocess.run(
        [str(ADB), "-s", "emulator-5554", *args],
        env=ENV,
        capture_output=True,
        check=True,
        timeout=60,
    )
    return result.stdout if binary else result.stdout.decode().strip()


def tree():
    adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
    return ET.fromstring(adb("exec-out", "cat", "/sdcard/window.xml"))


def find(text, timeout=15, scroll=False, button=False):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = tree()
        matches = [
            node
            for node in root.iter("node")
            if text.casefold() in node.get("text", "").casefold()
            or text.casefold() in node.get("content-desc", "").casefold()
        ]
        if button:
            matches = [
                node
                for node in matches
                if node.get("class", "").endswith("Button")
                and node.get("enabled") == "true"
            ]
        if matches:
            return matches[0]
        if scroll:
            adb("shell", "input", "swipe", "550", "1950", "550", "650", "350")
        time.sleep(0.4)
    raise AssertionError(f"Missing UI: {text}")


def tap(node):
    left, top, right, bottom = map(int, re.findall(r"\d+", node.get("bounds")))
    adb("shell", "input", "tap", str((left + right) // 2), str((top + bottom) // 2))


def screenshot(name):
    (ARTIFACTS / name).write_bytes(adb("exec-out", "screencap", "-p", binary=True))


def snapshot():
    adb("shell", "am", "force-stop", PACKAGE)
    directory = Path(tempfile.mkdtemp(prefix="android-cache-check-"))
    name = "media-cleaner.sqlite3"
    for suffix in ["", "-wal"]:
        try:
            (directory / (name + suffix)).write_bytes(
                adb(
                    "exec-out",
                    "run-as",
                    PACKAGE,
                    "cat",
                    "databases/" + name + suffix,
                    binary=True,
                )
            )
        except subprocess.CalledProcessError:
            if not suffix:
                raise
    return sqlite3.connect(directory / name)


def launch(scan=False):
    args = ["shell", "am", "start", "-n", PACKAGE + "/.MainActivity"]
    if scan:
        args += ["--ez", "fixtureScan", "true"]
    adb(*args)


assert adb("emu", "avd", "name").splitlines()[0] == "media-cleaner-test", (
    "Only the isolated synthetic fixture AVD is allowed"
)
adb("shell", "svc", "wifi", "disable")
adb("shell", "settings", "put", "global", "window_animation_scale", "0")
adb("shell", "settings", "put", "global", "transition_animation_scale", "0")
adb("shell", "settings", "put", "global", "animator_duration_scale", "0")
adb("shell", "wm", "size", "1080x2400")
adb("shell", "input", "keyevent", "KEYCODE_WAKEUP")
adb("shell", "input", "keyevent", "82")
adb("shell", "pm", "clear", PACKAGE)
for permission in ["READ_MEDIA_IMAGES", "READ_MEDIA_VIDEO", "POST_NOTIFICATIONS"]:
    adb("shell", "pm", "grant", PACKAGE, "android.permission." + permission)
with tempfile.TemporaryDirectory(prefix="android-media-fixture-") as temp:
    temp = Path(temp)
    image = Image.new("RGB", (320, 200), "#426e93")
    draw = ImageDraw.Draw(image)
    rng = random.Random(19)
    for _ in range(40):
        x, y = rng.randrange(290), rng.randrange(170)
        draw.rectangle(
            (x, y, x + 30, y + 30), fill=tuple(rng.randrange(256) for _ in range(3))
        )
    image.save(temp / "trip.png")
    (temp / "trip copy.png").write_bytes((temp / "trip.png").read_bytes())
    image.resize((160, 100)).save(temp / "trip resized.jpg", quality=90)
    frames = temp / "frames"
    frames.mkdir()
    for i in range(24):
        frame = image.copy()
        ImageDraw.Draw(frame).rectangle((i * 6, 30, i * 6 + 40, 75), fill=(250, 50, 70))
        frame.save(frames / f"frame{i:03d}.png")
    for name, size in [
        ("clip-original.mp4", "240:150"),
        ("clip-reencoded.mp4", "160:100"),
    ]:
        subprocess.run(
            [
                executable("ffmpeg"),
                "-v",
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
                "-vf",
                "scale=" + size,
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(temp / name),
            ],
            check=True,
            timeout=30,
        )
    gallery = "/sdcard/Pictures/MediaCleanerFixture"
    adb("shell", "mkdir", "-p", gallery)
    for file in temp.iterdir():
        if file.is_file():
            adb("push", str(file), gallery + "/" + file.name)
            adb(
                "shell",
                "am",
                "broadcast",
                "-a",
                "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
                "-d",
                "file://" + quote(gallery + "/" + file.name),
            )
    print("Scanning real synthetic photos and videos", flush=True)
    launch(scan=True)
    find("Scan complete.", timeout=180)
    screenshot("scanner.png")
    db = snapshot()
    meta = dict(db.execute("SELECT key,value FROM meta"))
    assert meta["status"] == "completed", meta
    assert meta["errors"] == "0", meta
    assert int(meta["total"]) >= 5, meta
    groups = db.execute("SELECT classification,uris FROM groups").fetchall()
    assert any(
        kind == "EXACT_DUPLICATE" and len(json.loads(uris)) == 2
        for kind, uris in groups
    ), groups
    assert any(
        kind == "SIMILAR_CONTENT" and len(json.loads(uris)) == 3
        for kind, uris in groups
    ), groups
    video_uris = {
        row[0] for row in db.execute("SELECT uri FROM files WHERE kind='video'")
    }
    assert any(
        kind == "SIMILAR_CONTENT" and set(json.loads(uris)) == video_uris
        for kind, uris in groups
    ), groups
    db.close()
    print("Checking persisted file checkpoint reuse", flush=True)
    launch(scan=True)
    find("Scan complete.", timeout=90)
    db = snapshot()
    meta = dict(db.execute("SELECT key,value FROM meta"))
    assert int(meta["cached"]) == int(meta["total"]), meta
    db.close()
    print("Checking comparison playback and saved selection", flush=True)
    launch()
    tap(find("Compare similar videos", scroll=True, timeout=40))
    find("Play all")
    screenshot("video-comparison.png")
    tap(find("Play all", button=True))
    time.sleep(1)
    screenshot("comparison-playing.png")
    tap(find("Pause all"))
    tap(find("Select clip-reencoded.mp4 for deletion"))
    tap(find("Select clip-original.mp4 for deletion"))
    find("Keep at least one file")
    tap(find("OK"))
    tap(find("Close comparison", scroll=True, timeout=25))
    tap(find("Delete selected videos (1)", scroll=True, timeout=35))
    print("Checking app and Android cleanup confirmations", flush=True)
    confirm = find("Continue to Android confirmation")
    assert confirm.get("enabled") == "false", "Cleanup confirmation was bypassed"
    screenshot("cleanup-preview.png")
    tap(find("Cancel"))
    tap(find("Delete selected videos (1)", scroll=True, timeout=35))
    find("Confirm group cleanup")
    tap(find("I reviewed these files"))
    tap(find("Continue to Android confirmation"))
    # This is the Android MediaProvider dialog, not an application confirmation.
    system_tree = tree()
    if not any(
        node.get("package", "").startswith("com.google.android.providers.media")
        or node.get("package", "").startswith("com.android.providers.media")
        for node in system_tree.iter("node")
    ):
        time.sleep(2)
    screenshot("android-trash-confirmation.png")
    tap(find("Allow", timeout=20, button=True))
    find("trashed ·", scroll=True, timeout=30)
    assert "clip-reencoded.mp4" not in adb("shell", "ls", gallery).splitlines()
    assert "clip-original.mp4" in adb("shell", "ls", gallery).splitlines()
    screenshot("cleanup-history.png")
    tap(find("Restore from Trash"))
    tap(find("Continue"))
    tap(find("Allow", timeout=20, button=True))
    find("restored ·", scroll=True, timeout=30)
    assert "clip-reencoded.mp4" in adb("shell", "ls", gallery).splitlines()
    screenshot("restored.png")
print(
    "Android emulator smoke passed: real photo/video matching, saved checkpoints, comparison selections, explicit confirmation, Android Trash, restore."
)
