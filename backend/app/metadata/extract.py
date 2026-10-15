import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image, ExifTags
from pillow_heif import register_heif_opener
from app.core.filesystem import RAW_EXTENSIONS

register_heif_opener()


def tools() -> dict[str, bool]:
    return {tool: shutil.which(tool) is not None for tool in ("ffprobe", "ffmpeg", "exiftool")}


def extract(path: Path, media_type: str) -> tuple[dict, list[str]]:
    fields: dict = {}
    warnings: list[str] = []
    if media_type == "image" and path.suffix.lower() not in RAW_EXTENSIONS:
        try:
            with Image.open(path) as image:
                exif = {
                    ExifTags.TAGS.get(key, str(key)): str(value) for key, value in image.getexif().items()
                }
                fields.update(
                    width=image.width,
                    height=image.height,
                    format=image.format,
                    mode=image.mode,
                    animated=bool(getattr(image, "is_animated", False)),
                    frames=getattr(image, "n_frames", 1),
                    exif=exif,
                    orientation=exif.get("Orientation"),
                    capture_timestamp=exif.get("DateTimeOriginal"),
                    camera_manufacturer=exif.get("Make"),
                    camera_model=exif.get("Model"),
                    color_profile=bool(image.info.get("icc_profile")),
                )
        except Exception as exc:
            warnings.append(f"Image metadata unavailable: {type(exc).__name__}")
    if media_type == "video":
        if not shutil.which("ffprobe"):
            warnings.append("FFprobe unavailable; exact hashing still works")
        else:
            try:
                process = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                    capture_output=True,
                    timeout=30,
                    check=True,
                )
                raw = json.loads(process.stdout)
                video = [stream for stream in raw.get("streams", []) if stream.get("codec_type") == "video"]
                audio = [stream for stream in raw.get("streams", []) if stream.get("codec_type") == "audio"]
                stream = video[0] if video else {}
                container = raw.get("format", {})
                fields.update(
                    width=stream.get("width"),
                    height=stream.get("height"),
                    duration=container.get("duration"),
                    frame_rate=stream.get("avg_frame_rate"),
                    video_codec=stream.get("codec_name"),
                    audio_codec=audio[0].get("codec_name") if audio else None,
                    bitrate=container.get("bit_rate"),
                    container=container.get("format_name"),
                    video_stream_count=len(video),
                    audio_stream_count=len(audio),
                    raw=raw,
                )
            except (OSError, ValueError, subprocess.SubprocessError):
                warnings.append("FFprobe failed or timed out; exact hashing still works")
    if shutil.which("exiftool"):
        try:
            process = subprocess.run(
                ["exiftool", "-json", "-n", str(path)], capture_output=True, timeout=30, check=True
            )
            fields["exiftool"] = json.loads(process.stdout)[0]
        except (OSError, ValueError, IndexError, subprocess.SubprocessError):
            warnings.append("ExifTool metadata unavailable")
    elif path.suffix.lower() in RAW_EXTENSIONS:
        warnings.append("RAW decoding is deferred; install ExifTool for embedded metadata")
    return fields, warnings
