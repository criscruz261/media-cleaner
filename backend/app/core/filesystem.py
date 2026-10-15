import hashlib
import os
from pathlib import Path
from dataclasses import dataclass

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
    ".gif",
    ".avif",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".orf",
    ".rw2",
}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".3gp",
    ".mpeg",
    ".mpg",
    ".ts",
    ".mts",
    ".m2ts",
    ".insv",
    ".lrv",
}
RAW_EXTENSIONS = {".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2"}


@dataclass(frozen=True)
class Identity:
    device: str
    inode: str
    size: int
    mtime_ns: str
    ctime_ns: str

    def key(self, path: str) -> str:
        return hashlib.sha256(f"{path}|{self}".encode()).hexdigest()


def identity(path: Path) -> Identity:
    if path.is_symlink() or path.resolve(strict=True) != path.absolute():
        raise ValueError("Symlinks or changed parent paths are not allowed")
    info = path.stat()
    if not path.is_file():
        raise ValueError("Expected a regular file")
    return Identity(
        str(info.st_dev), str(info.st_ino), info.st_size, str(info.st_mtime_ns), str(info.st_ctime_ns)
    )


def stored_identity(file) -> Identity:
    return Identity(file.device, file.inode, file.size, file.mtime_ns, file.ctime_ns)


def contained(path: Path, roots: list[str]) -> bool:
    return any(path.is_relative_to(Path(root).expanduser().resolve()) for root in roots)


def protection(path: Path, protected: list[str]) -> str | None:
    if contained(path, protected):
        return "Protected directory"
    if path.suffix.lower() in RAW_EXTENSIONS:
        return "RAW original: cleanup is protected in Phase 1"
    # A filename is not proof of pairing. Conservatively protect potential pairs.
    companions = VIDEO_EXTENSIONS if path.suffix.lower() in IMAGE_EXTENSIONS else IMAGE_EXTENSIONS
    for extension in companions:
        if any(path.with_suffix(suffix).exists() for suffix in {extension, extension.upper()}):
            return "Possible photo/video companion: review outside automatic cleanup"
    return None


def mount_root(path: Path) -> Path:
    current = path if path.is_dir() else path.parent
    while current.parent != current and current.parent.stat().st_dev == current.stat().st_dev:
        current = current.parent
    return current


def volume_key(path: Path) -> tuple[str, str]:
    mount = mount_root(path)
    info = mount.stat()
    # Device/inode is session identity, not a portable hardware UUID. Never infer deletions from absence.
    return f"{os.name}:{info.st_dev}:{info.st_ino}", str(mount)
