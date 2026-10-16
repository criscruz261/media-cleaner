import os
from pathlib import Path
from collections.abc import Callable, Iterator
from app.core.filesystem import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, contained


def discover(
    root: Path, options: dict, checkpoint: Callable[[], None], on_error: Callable[[str], None]
) -> Iterator[Path]:
    excluded = options["excluded_directories"]
    extensions = (
        IMAGE_EXTENSIONS
        if options["mode"] == "images"
        else VIDEO_EXTENSIONS
        if options["mode"] == "videos"
        else IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    )
    extensions = extensions - set(options["excluded_extensions"])

    def walk(directory: Path):
        checkpoint()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    checkpoint()
                    if entry.is_symlink() or entry.name in {
                        ".media-cleaner-quarantine",
                        ".media-cleaner-cache",
                    }:
                        continue
                    if not options["include_hidden"] and entry.name.startswith("."):
                        continue
                    path = Path(entry.path)
                    if contained(path, excluded):
                        continue
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            yield from walk(path)
                        elif path.suffix.lower() in extensions and entry.is_file(follow_symlinks=False):
                            yield path
                    except OSError as exc:
                        on_error(type(exc).__name__)
        except OSError as exc:
            on_error(type(exc).__name__)

    yield from walk(root)
