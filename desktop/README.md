# Desktop release boundary · Phase 5

No Tauri shell or installer is claimed in Phase 1. The current development application runs a loopback Python backend serving the built React frontend.

The planned release shell is Tauri 2. It must spawn a bundled, per-platform Python sidecar, pass an ephemeral session token and selected loopback port, wait for readiness, load only that origin, and terminate/join the process on window close. Do not enable arbitrary shell access from the renderer. A packaging spike must verify sidecar process-tree shutdown and app-data permissions on every supported OS.

For packaged builds, use a per-platform PyInstaller (or equivalent validated Python bundling) build to include Python, Pillow/HEIF libraries and backend modules plus Alembic migrations, with separately licensed FFmpeg/FFprobe and ExifTool resources. Users must not need to install Python manually in release builds. Sign and notarize macOS arm64/x64 bundles, sign Windows installers, and build/test Linux packages against supported glibc versions. Codec licenses, executable signatures, updates, native Trash behavior, external drives and uninstall retention need release validation.

The supplied scripts are development installation, not a claim that the desktop packaging acceptance criteria are met.
