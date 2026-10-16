"""Multi-frame descriptors for video and animated images; no runtime downloads."""

from collections.abc import Callable
from io import BytesIO
import json
import math
from fractions import Fraction
from pathlib import Path
from PIL import Image
from app.core.media_tools import executable, run_media
from app.similarity.images import describe_image, Signature, PRESETS

ALGORITHM = "temporal-phash-dhash"
VERSION = "2"
SAMPLE_COUNT = 9
MIN_MATCHES = 6
DURATION_TOLERANCE = {"strict": 0.01, "balanced": 0.03, "broad": 0.06}
MATCH_RATIO = {"strict": 1.0, "balanced": 0.85, "broad": 0.75}


def is_animation(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            return image.format in {"GIF", "PNG", "WEBP", "AVIF", "HEIF"} and bool(
                getattr(image, "is_animated", False)
            )
    except Exception:
        return False


def temporal_kind(path: Path, media_type: str) -> bool:
    return media_type == "video" or is_animation(path)


def probe_video(path: Path, checkpoint: Callable[[], None] = lambda: None) -> dict:
    tool = executable("ffprobe")
    if not tool:
        raise ValueError("FFprobe is missing. Run scripts/install-media-tools.py during setup.")
    output = run_media(
        [
            tool,
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,duration,avg_frame_rate:format=duration,format_name",
            "-of",
            "json",
            str(path),
        ],
        checkpoint,
    )
    info = json.loads(output)
    streams = info.get("streams", [])
    if not streams:
        raise ValueError("No decodable video stream")
    stream = streams[0]
    raw_duration = stream.get("duration")
    if raw_duration in {None, "N/A"}:
        raw_duration = info.get("format", {}).get("duration")
    duration = float(raw_duration or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Video duration is unavailable")
    try:
        interval = 1 / float(Fraction(stream.get("avg_frame_rate", "0/1")))
        if not math.isfinite(interval) or interval <= 0:
            interval = 0.04
    except (ValueError, ZeroDivisionError):
        interval = 0.04
    return {
        "frame_interval": interval,
        "duration": duration,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "codec": stream.get("codec_name"),
        "container": info.get("format", {}).get("format_name"),
    }


def sample_video_frame(
    path: Path, timestamp: float, checkpoint: Callable[[], None] = lambda: None
) -> Image.Image | None:
    tool = executable("ffmpeg")
    if not tool:
        raise ValueError("FFmpeg is missing. Run scripts/install-media-tools.py during setup.")
    data = run_media(
        [
            tool,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-threads",
            "1",
            "-filter_threads",
            "1",
            "-protocol_whitelist",
            "file,pipe",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-frames:v",
            "1",
            "-an",
            "-sn",
            "-vf",
            "scale=w='if(gte(dar,1),256,max(1,trunc(256*dar)))':h='if(gte(dar,1),max(1,trunc(256/dar)),256)',setsar=1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "pipe:1",
        ],
        checkpoint,
    )
    if not data:
        return None
    with Image.open(BytesIO(data)) as image:
        return image.convert("RGB")


def finish_descriptor(duration: float, frames: list[dict], kind: str, **metadata) -> dict:
    distinct = {(frame["phash"], frame["dhash"]) for frame in frames}
    if len(frames) < MIN_MATCHES or len(distinct) < 2:
        return {
            "skipped": "Not enough informative, changing frames for sequence similarity; exact matching still works."
        }
    return {"duration": duration, "frames": frames, "kind": kind, "sample_count": SAMPLE_COUNT, **metadata}


def fingerprint_video(path: Path, checkpoint: Callable[[], None] = lambda: None, progress=None) -> dict:
    metadata = probe_video(path, checkpoint)
    duration = metadata.pop("duration")
    frame_interval = metadata.pop("frame_interval")
    frames = []
    for slot in range(SAMPLE_COUNT):
        if progress:
            progress(slot, SAMPLE_COUNT)
        checkpoint()
        timestamp = duration * (slot + 0.5) / SAMPLE_COUNT
        # FFmpeg accurate seeking yields the next frame. Offset one frame interval
        # to sample the frame displayed at the requested time, including the last interval.
        image = sample_video_frame(path, max(0, timestamp - frame_interval + 1e-6), checkpoint)
        descriptor = describe_image(image) if image is not None else None
        if descriptor:
            frames.append({"slot": slot, "time": timestamp, **descriptor})
    return finish_descriptor(duration, frames, "video", **metadata)


def fingerprint_animation(path: Path, checkpoint: Callable[[], None] = lambda: None, progress=None) -> dict:
    with Image.open(path) as image:
        count = image.n_frames
        if count > 2000:
            return {"skipped": "Animation exceeds 2000-frame analysis limit; exact matching still works."}
        durations = []
        for index in range(count):
            checkpoint()
            image.seek(index)
            image.load()
            duration = float(image.info.get("duration", 0)) / 1000
            if not math.isfinite(duration) or duration <= 0:
                return {"skipped": "Animation frame timing is unavailable; exact matching still works."}
            durations.append(duration)
        duration = sum(durations)
        frames, current, boundary = [], 0, durations[0]
        for slot in range(SAMPLE_COUNT):
            if progress:
                progress(slot, SAMPLE_COUNT)
            checkpoint()
            timestamp = duration * (slot + 0.5) / SAMPLE_COUNT
            while current < count - 1 and timestamp >= boundary:
                current += 1
                boundary += durations[current]
            image.seek(current)
            descriptor = describe_image(image.convert("RGB"))
            if descriptor:
                frames.append({"slot": slot, "time": timestamp, **descriptor})
        return finish_descriptor(duration, frames, "animation", source_frames=count)


def duration_tolerance(duration: float, sensitivity: str) -> float:
    return max(0.25, duration * DURATION_TOLERANCE[sensitivity])


def compare_sequences(left: dict, right: dict, sensitivity: str) -> dict | None:
    if "frames" not in left or "frames" not in right:
        return None
    if abs(left["duration"] - right["duration"]) > duration_tolerance(
        min(left["duration"], right["duration"]), sensitivity
    ):
        return None
    a, b = (
        {frame["slot"]: Signature.from_value(frame) for frame in value["frames"]} for value in (left, right)
    )
    common = a.keys() & b.keys()
    if len(common) < MIN_MATCHES:
        return None
    matched = []
    for slot in sorted(common):
        if a[slot].compatible(b[slot], PRESETS[sensitivity]):
            p, d = a[slot].distances(b[slot])
            matched.append({"slot": slot, "phash_distance": p, "dhash_distance": d})
    required = max(MIN_MATCHES, math.ceil(len(common) * MATCH_RATIO[sensitivity]))
    if len(matched) < required:
        return None
    # Repeated title cards or a single shared static frame cannot establish a sequence match.
    if len({(a[item["slot"]].phash, a[item["slot"]].dhash) for item in matched}) < 2:
        return None
    return {
        "algorithm": ALGORITHM,
        "version": VERSION,
        "matched_samples": len(matched),
        "compared_samples": len(common),
        "required_samples": required,
        "sample_count": SAMPLE_COUNT,
        "duration_difference_seconds": abs(left["duration"] - right["duration"]),
        "samples": matched,
        "note": "Sampled visual sequence only. Audio is not compared; review playback and sound before removal.",
    }
