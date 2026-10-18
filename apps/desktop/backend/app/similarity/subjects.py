"""Local learned features for subject/scene variation, with a metric candidate index."""

import base64
import atexit
from functools import lru_cache
import math
from pathlib import Path
import threading
import numpy as np

MODEL = "mobilenet-v3-small-imagenet-float32-v1"
LIMITS = {4: None, 8: 0.98, 12: 0.95, 16: 0.91, 20: 0.86, 24: 0.80}
_lock = threading.RLock()
_embedder = None


def describe(image):
    global _embedder
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions, vision

    with _lock:
        if _embedder is None:
            _embedder = vision.ImageEmbedder.create_from_options(
                vision.ImageEmbedderOptions(
                    base_options=BaseOptions(
                        model_asset_path=str(
                            Path(__file__).parents[1] / "assets" / "subject_embedder.tflite"
                        ),
                        delegate=BaseOptions.Delegate.CPU,
                    ),
                    l2_normalize=True,
                )
            )
        value = (
            _embedder.embed(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image.convert("RGB"))))
            .embeddings[0]
            .embedding
        )
    encoded = np.rint(np.clip(value, -1, 1) * 127).astype(np.int8).tobytes()
    return base64.b64encode(encoded).decode("ascii")


def regions(image):
    width, height = image.size
    if min(width, height) < 2:
        return []
    return [
        describe(image.crop((x * width // 2, y * height // 2, (x + 1) * width // 2, (y + 1) * height // 2)))
        for y in range(2)
        for x in range(2)
    ]


def compatible_regions(left, right, whole_score, p_limit):
    if p_limit < 16 or whole_score < 0.40 or len(left) != 4 or len(right) != 4:
        return False
    limit = {16: 0.97, 20: 0.94, 24: 0.90}[p_limit]
    return sum(cosine(a, b) >= limit for a, b in zip(left, right)) >= 2


@lru_cache(maxsize=4096)
def vector(encoded: bytes):
    values = np.frombuffer(encoded, dtype=np.int8).astype(np.float32)
    norm = float(np.linalg.norm(values))
    return values / norm if norm else values


def cosine(left: bytes, right: bytes):
    if not left or len(left) != len(right):
        return -1.0
    return min(1.0, max(-1.0, float(np.dot(vector(left), vector(right)))))


class SubjectIndex:
    """BK-tree of quantized Euclidean distances on normalized learned vectors.

    Expand searches by one distance bin to cover distance rounding. Full cosine
    checks and complete-link validation still decide membership.
    """

    def __init__(self):
        self.root = None

    @staticmethod
    def distance(left, right):
        return int(100 * math.sqrt(max(0, 2 - 2 * cosine(left, right))))

    def add(self, value, group):
        if not value:
            return
        if self.root is None:
            self.root = [value, [group], {}]
            return
        node = self.root
        while True:
            distance = self.distance(value, node[0])
            if value == node[0]:
                node[1].append(group)
                return
            if distance not in node[2]:
                node[2][distance] = [value, [group], {}]
                return
            node = node[2][distance]

    def search(self, value, limit):
        if not value or limit is None:
            return
        radius = math.ceil(100 * math.sqrt(2 - 2 * limit)) + 1
        pending = [self.root] if self.root is not None else []
        while pending:
            node = pending.pop()
            distance = self.distance(value, node[0])
            if distance <= radius:
                yield from node[1]
            pending.extend(
                child for edge, child in node[2].items() if distance - radius <= edge <= distance + radius
            )


@atexit.register
def close():
    global _embedder
    with _lock:
        if _embedder is not None:
            _embedder.close()
            _embedder = None
