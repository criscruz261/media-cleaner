import hashlib
from pathlib import Path
from collections.abc import Callable
from app.core.filesystem import identity, Identity


class ScanStopped(Exception):
    pass


def hash_file(path: Path, expected: Identity, checkpoint: Callable[[], None] = lambda: None) -> str:
    if identity(path) != expected:
        raise ValueError("File changed before hashing")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            checkpoint()
            digest.update(chunk)
    if identity(path) != expected:
        raise ValueError("File changed during hashing")
    return digest.hexdigest()
