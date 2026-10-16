"""Compatibility entry point for desktop tooling."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[1] / "apps/desktop/scripts/install-media-tools.py"), run_name="__main__")
