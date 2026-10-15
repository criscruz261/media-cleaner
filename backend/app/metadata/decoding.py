"""Bounded preview decoding, including embedded camera RAW thumbnails."""

from io import BytesIO
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
from app.core.filesystem import RAW_EXTENSIONS


def load_still(path: Path) -> Image.Image:
    if path.suffix.lower() not in RAW_EXTENSIONS:
        with Image.open(path) as source:
            source.draft("RGB", (1600, 1600))
            source.thumbnail((1600, 1600))
            return ImageOps.exif_transpose(source).convert("RGB")
    import rawpy

    with rawpy.imread(str(path)) as raw:
        try:
            thumbnail = raw.extract_thumb()
            if thumbnail.format == rawpy.ThumbFormat.JPEG:
                with Image.open(BytesIO(thumbnail.data)) as image:
                    image.thumbnail((1600, 1600))
                    oriented = bool(image.getexif().get(274))
                    decoded = ImageOps.exif_transpose(image).convert("RGB")
            else:
                decoded = Image.fromarray(thumbnail.data)
                oriented = False
            if not oriented:
                rotation = {
                    3: Image.Transpose.ROTATE_180,
                    5: Image.Transpose.ROTATE_90,
                    6: Image.Transpose.ROTATE_270,
                }.get(raw.sizes.flip)
                if rotation is not None:
                    decoded = decoded.transpose(rotation)
        except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
            if raw.sizes.width * raw.sizes.height > Image.MAX_IMAGE_PIXELS:
                raise UnidentifiedImageError("RAW is too large for safe fallback decoding")
            decoded = Image.fromarray(raw.postprocess(half_size=True, output_bps=8, use_camera_wb=True))
        decoded.thumbnail((1600, 1600))
        return decoded
