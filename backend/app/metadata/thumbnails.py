"""Small identity-keyed in-memory thumbnails; requests validate the source snapshot."""

from functools import lru_cache
from io import BytesIO
from pathlib import Path
from app.metadata.decoding import load_still
from app.similarity.temporal import sample_video_frame


@lru_cache(maxsize=128)
def thumbnail(path: str, snapshot: str, media_type: str) -> bytes:
    image = sample_video_frame(Path(path), 0) if media_type == "video" else load_still(Path(path))
    if image is None:
        raise ValueError("No video frame available")
    image.thumbnail((480, 320))
    output = BytesIO()
    image.convert("RGB").save(output, "JPEG", quality=80)
    return output.getvalue()
