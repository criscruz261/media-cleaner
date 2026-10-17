import os
from pathlib import Path
from collections.abc import Callable, Iterator
from app.core.filesystem import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, contained


def ignored_directory(name: str) -> bool:
    name = name.casefold()
    return name in {
        "$recycle.bin",
        "recycler",
        "recycled",
        ".trash",
        ".trashes",
        ".media-cleaner-quarantine",
        ".media-cleaner-cache",
    } or (name.startswith(".trash-") and name[7:].isdigit())


def discover(
    root: Path, options: dict, checkpoint: Callable[[], None], on_error: Callable[[str], None]
) -> Iterator[Path]:
    # Also exclude a trash/cache directory when entered directly as a scan root.
    if any(ignored_directory(part) for part in root.parts):
        return
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
                    if entry.is_symlink() or ignored_directory(entry.name):
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
                            if entry.stat(follow_symlinks=False).st_size > 0:
                                yield path
                    except OSError as exc:
                        on_error(type(exc).__name__)
        except OSError as exc:
            on_error(type(exc).__name__)

    yield from walk(root)
