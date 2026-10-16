"""Explicit setup-time download; runtime media scanning never downloads tools."""

import shutil
from static_ffmpeg import run

if shutil.which("ffmpeg") and shutil.which("ffprobe"):
    print("FFmpeg and FFprobe already available on PATH.")
else:
    ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_raise()
    print(f"Installed FFmpeg: {ffmpeg}\nInstalled FFprobe: {ffprobe}")
