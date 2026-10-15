"""Find tools already installed by setup; never fetch binaries during scanning."""

import importlib.util
import os
from pathlib import Path
import platform
import shutil
import sys
import subprocess
import time
from collections.abc import Callable


def executable(name: str) -> str | None:
    override = os.environ.get("MEDIA_CLEANER_" + name.upper())
    if override:
        return override if Path(override).is_file() else None
    found = shutil.which(name)
    if found:
        return found
    if name not in {"ffmpeg", "ffprobe"}:
        return None
    spec = importlib.util.find_spec("static_ffmpeg")
    if not spec or not spec.origin:
        return None
    key = sys.platform
    if key in {"darwin", "linux"} and platform.machine().lower() in {"arm64", "aarch64"}:
        key += "_arm64"
    path = Path(spec.origin).parent / "bin" / key / (name + (".exe" if sys.platform == "win32" else ""))
    return str(path) if path.is_file() else None


def run_media(
    command: list[str], checkpoint: Callable[[], None] = lambda: None, timeout: float = 30
) -> bytes:
    """Check cancellation while decoder processes run, and always reap them."""
    checkpoint()
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    deadline = time.monotonic() + timeout
    try:
        while True:
            checkpoint()
            if time.monotonic() >= deadline:
                raise ValueError("Media decoding timed out")
            try:
                stdout, stderr = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ValueError("Media decoder failed or codec is unsupported")
        if len(stdout) > 2 * 1024 * 1024:
            raise ValueError("Media decoder output exceeded the preview limit")
        return stdout
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate()
