import hashlib
from pathlib import Path
from collections.abc import Callable
from app.core.filesystem import identity, Identity


class ScanStopped(Exception):
    pass


def hash_file(
    path: Path,
    expected: Identity,
    checkpoint: Callable[[], None] = lambda: None,
    progress: Callable[[int], None] | None = None,
) -> str:
    if identity(path) != expected:
        raise ValueError("File changed before hashing")
    digest = hashlib.sha256()
    read_bytes = 0
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            checkpoint()
            digest.update(chunk)
            read_bytes += len(chunk)
            if progress:
                progress(read_bytes)
    if identity(path) != expected:
        raise ValueError("File changed during hashing")
    return digest.hexdigest()
