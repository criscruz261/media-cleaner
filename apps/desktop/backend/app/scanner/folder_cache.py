"""Portable per-file analysis checkpoints under the selected media roots."""

import json
import math
import os
from pathlib import Path
import tempfile
from app.similarity.images import Signature, ALGORITHM, VERSION
from app.similarity import temporal

CACHE_NAME = ".media-cleaner-cache"
MAX_ENTRY = 1024 * 1024


def location(path: Path, roots: list[str], key: str) -> Path:
    root = max(
        (Path(root) for root in roots if path.is_relative_to(Path(root))), key=lambda root: len(root.parts)
    )
    directory = root / CACHE_NAME / key[:2]
    for parent in [root / CACHE_NAME, directory]:
        if parent.is_symlink() or parent.resolve() != parent.absolute():
            raise ValueError("Cache directory contains a symlink")
    return directory / (key + ".json")


def valid_signature(value):
    signature = Signature.from_value(value)
    return (
        0 <= signature.phash < 2**64
        and 0 <= signature.dhash < 2**64
        and math.isfinite(signature.aspect)
        and signature.aspect > 0
        and len(signature.color) == 3
        and all(math.isfinite(color) and 0 <= color <= 255 for color in signature.color)
    )


def valid_descriptor(algorithm, version, value):
    if not isinstance(value, dict):
        return False
    if (algorithm, version) not in {(ALGORITHM, VERSION), (temporal.ALGORITHM, temporal.VERSION)}:
        return False
    if isinstance(value.get("skipped"), str):
        return set(value) <= {"skipped", "sample_count"}
    if algorithm == ALGORITHM:
        return valid_signature(value)
    duration, frames = value["duration"], value["frames"]
    sample_count = value.get("sample_count", 9)
    return (
        isinstance(duration, (int, float))
        and math.isfinite(duration)
        and duration > 0
        and value["kind"] in {"video", "animation"}
        and isinstance(frames, list)
        and type(sample_count) is int
        and 6 <= sample_count <= 24
        and 0 < len(frames) <= sample_count
        and len({frame["slot"] for frame in frames}) == len(frames)
        and all(
            type(frame["slot"]) is int and 0 <= frame["slot"] < sample_count and valid_signature(frame)
            for frame in frames
        )
    )


def read(path: Path, roots: list[str], key: str) -> dict | None:
    try:
        entry = location(path, roots, key)
        descriptor = os.open(entry, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as source:
            raw = source.read(MAX_ENTRY + 1)
        if len(raw) > MAX_ENTRY:
            return None
        data = json.loads(raw)
        if data["version"] != 1 or data["identity_key"] != key:
            return None
        digest = data["digest"]
        if digest is not None and (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(c not in "0123456789abcdef" for c in digest)
        ):
            return None
        if (
            not isinstance(data["fields"], dict)
            or not isinstance(data["warnings"], list)
            or not all(isinstance(item, str) for item in data["warnings"])
        ):
            return None
        data["fingerprints"] = [
            item
            for item in data["fingerprints"]
            if valid_descriptor(item["algorithm"], item["version"], item["value"])
        ]
        data["choices"] = {
            kind: keep
            for kind, keep in data["choices"].items()
            if kind in {"EXACT_DUPLICATE", "SIMILAR_CONTENT"} and type(keep) is bool
        }
        return data
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError):
        return None


def write(path: Path, roots: list[str], key: str, data: dict):
    entry = location(path, roots, key)
    entry.parent.mkdir(parents=True, exist_ok=True)
    if entry.is_symlink():
        raise ValueError("Cache entry is a symlink")
    previous = read(path, roots, key)
    if previous:
        # An exact-only scan must not discard expensive similarity descriptors.
        descriptors = {(item["algorithm"], item["version"]): item for item in previous["fingerprints"]}
        descriptors.update({(item["algorithm"], item["version"]): item for item in data["fingerprints"]})
        data = {
            **data,
            "digest": data["digest"] or previous["digest"],
            "fingerprints": list(descriptors.values()),
            "choices": {**previous["choices"], **data["choices"]},
        }
    payload = json.dumps({"version": 1, "identity_key": key, **data}, allow_nan=False).encode()
    if len(payload) > MAX_ENTRY:
        raise ValueError("Cache entry exceeds size limit")
    descriptor, temporary = tempfile.mkstemp(prefix=".checkpoint-", dir=entry.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, entry)
    finally:
        Path(temporary).unlink(missing_ok=True)
