import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "event": record.getMessage(),
                "scan_id": getattr(record, "scan_id", None),
            },
            ensure_ascii=False,
        )


def configure(directory: Path):
    logger = logging.getLogger("media_cleaner")
    logger.setLevel(logging.INFO)
    target = str(directory / "diagnostics.jsonl")
    for existing in list(logger.handlers):
        if getattr(existing, "baseFilename", None) != target:
            logger.removeHandler(existing)
            existing.close()
    if not logger.handlers:
        handler = RotatingFileHandler(directory / "diagnostics.jsonl", maxBytes=2_000_000, backupCount=2)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
