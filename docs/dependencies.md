# Dependencies and platforms

Python dependencies are pinned in `apps/desktop/backend/requirements-dev.lock`; frontend dependencies are pinned in `apps/desktop/frontend/package-lock.json`. Source-compatible ranges live in pyproject/package.json. The local validation environment uses Python 3.12 and Node 22. Setup requires internet access to acquire dependencies. Normal analysis, previews and cleanup run locally without an account or network service.

| Dependency | Current use | Missing-tool behavior |
| --- | --- | --- |
| Python 3.12+, FastAPI, SQLAlchemy, Alembic, Pydantic | Backend and persistence | Required |
| Node 22.12+, React, TypeScript, Vite, Tailwind, TanStack Query | Development/frontend build | Required at setup/build; not for serving built assets |
| Pillow, pillow-heif | Image metadata, HEIC/HEIF and normalized previews | Installed Python requirements; codec support still varies |
| Send2Trash | OS Trash/Recycle Bin | Failed trash operation stays failed; no permanent-delete fallback |
| FFprobe (FFmpeg distribution) | Actual video-stream/container metadata | Per-file warning, exact hashing still available |
| ExifTool | Optional detailed EXIF/RAW metadata | Pillow/rawpy metadata remains available |
| FFmpeg | Time-spaced video frames for sequence similarity | Missing decoder is listed in scanner warnings |
| Zenity/KDialog | Linux native directory selection | Manual path entry available |

Install FFmpeg/ExifTool from their official distributions or your system package manager and put the executables on PATH: [FFmpeg download](https://ffmpeg.org/download.html), [ExifTool installation](https://exiftool.org/install.html). Typical package-manager packages are `ffmpeg` and `exiftool` (Ubuntu's ExifTool package is `libimage-exiftool-perl`). macOS can use Homebrew packages; Windows can use the official Windows distributions referenced by those projects. FFmpeg codec licensing and redistribution must be reviewed before packaging.

Native folder selection uses AppleScript on macOS, PowerShell Windows Forms on Windows and Zenity/KDialog on Linux. macOS may show a system filesystem-access dialog. Full desktop native dialogs and lifecycle integration will use Tauri in Phase 5. Windows/Linux behavior is implemented with portable APIs but requires actual platform CI and drive tests before release claims.

External filesystems vary: read-only drives cannot clean up, Trash may not exist on network mounts, some identity fields may be unreliable, and no-overwrite quarantine recovery requires hard-link support on that filesystem. Disconnected roots remain historical records, never treated as collection deletion. Device identity currently uses mount/device/inode context and may change after remount/reboot. The database itself should reside on local storage with reliable WAL semantics.

ImageHash and its NumPy/SciPy/PyWavelets dependencies are now installed and locked for similar-photo comparison. rawpy/LibRaw is installed for RAW thumbnails and decoding. The static-ffmpeg helper installs FFmpeg/FFprobe only during setup. OpenCV and embedding packages are not installed. They will be introduced with implemented/tested similarity or RAW decoding features. No optional model download occurs in this phase.

Setup now runs `scripts/install-media-tools.py`; scanning never downloads binaries. Tool lookup checks explicit MEDIA_CLEANER_FFMPEG/FFPROBE overrides, system PATH and the existing virtual-environment install. The helper obtains third-party platform binaries; see [media-similarity dependencies and limits](phase-3.md). RAW wheel availability and camera support vary by platform.
