from pathlib import Path
import os
import secrets
from platformdirs import user_data_path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    protected_directories: list[str] = Field(default_factory=list)
    excluded_directories: list[str] = Field(default_factory=list)
    excluded_extensions: list[str] = Field(default_factory=list)
    include_hidden: bool = False
    concurrency: int = Field(default=2, ge=1, le=8)
    cleanup_destination: str = "trash"
    theme: str = "system"


def data_directory() -> Path:
    return Path(
        os.environ.get("MEDIA_CLEANER_DATA", user_data_path("MediaCleaner", appauthor=False))
    ).resolve()


def authentication_token(directory: Path) -> str:
    path = directory / "api-token"
    if not path.exists():
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            handle.write(secrets.token_urlsafe(32))
    return path.read_text().strip()
