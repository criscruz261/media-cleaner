"""Temporary-only synthetic browser fixture server; never accepts real media paths."""

import json
from pathlib import Path
import secrets
import sys
import tempfile
from PIL import Image, ImageDraw
import random
import subprocess
import time
from app.core.media_tools import executable
import uvicorn
from app.api.main import create_app

with tempfile.TemporaryDirectory(prefix="media-cleaner-smoke-") as directory:
    root = Path(directory).resolve()
    media = root / "synthetic-media"
    media.mkdir()
    image = Image.new("RGB", (320, 200), "#6d8c63")
    similar = "--similar" in sys.argv
    if similar:
        randomizer = random.Random(19)
        draw = ImageDraw.Draw(image)
        for _ in range(40):
            x, y = randomizer.randrange(290), randomizer.randrange(170)
            draw.rectangle(
                (x, y, x + 30, y + 30),
                fill=tuple(randomizer.randrange(256) for _ in range(3)),
            )
        image.resize((160, 100)).save(media / "resized.jpg", quality=90)
    image.save(media / "IMG_0971.png")
    (media / "IMG_0971 copy.png").write_bytes((media / "IMG_0971.png").read_bytes())
    video = "--video" in sys.argv
    if video:
        frames = root / "video-frames"
        frames.mkdir()
        for number in range(24):
            frame = Image.new("RGB", (240, 160), "#426e93")
            draw = ImageDraw.Draw(frame)
            rng = random.Random(19)
            for _ in range(30):
                x, y = rng.randrange(210), rng.randrange(130)
                draw.rectangle(
                    (x, y, x + 25, y + 25),
                    fill=tuple(rng.randrange(256) for _ in range(3)),
                )
            draw.rectangle((number * 5, 30, number * 5 + 35, 70), fill=(250, 50, 70))
            frame.save(frames / f"frame{number:03d}.png")
        for name, scale, tone in [
            ("original.MOV", "240:160", "440"),
            ("reencoded.mp4", "120:80", "880"),
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
                    "-f",
                    "lavfi",
                    "-i",
                    f"sine=frequency={tone}:sample_rate=22050",
                    "-vf",
                    f"scale={scale}",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-shortest",
                    str(media / name),
                ],
                capture_output=True,
                check=True,
                timeout=30,
            )
    live = "--live" in sys.argv
    release = root / "release"
    if live:
        (media / "waiting.MOV").write_bytes(b"waiting")
    token = secrets.token_urlsafe(32)
    config = {
        "live": live,
        "release": str(release),
        "video": video,
        "similar": similar,
        "media": str(media),
        "token": token,
        "port": 18765,
        "artifacts": str(
            Path(__file__).resolve().parents[3] / ".tools" / "smoke-artifacts"
        ),
    }
    Path(sys.argv[1]).write_text(json.dumps(config))
    application = create_app(root / "data", token=token)
    if live:
        from app.database.models import File
        manager = application.state.manager
        process = manager.process_file

        def controlled(scan_id, file_id, checkpoint):
            with manager.sessions() as session:
                waiting = session.get(File, file_id).name == "waiting.MOV"
            while waiting and not release.exists():
                checkpoint()
                time.sleep(0.05)
            return process(scan_id, file_id, checkpoint)

        manager.process_file = controlled
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=config["port"],
        access_log=False,
    )
