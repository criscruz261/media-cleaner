# Desktop release boundary · Phase 5

## Portable Windows build

From Windows PowerShell at the repository root, run `./scripts/create-deploy-package.ps1`.
This reruns desktop setup, builds the frontend, installs pinned PyInstaller, and
bundles a console launcher, Python dependencies, frontend, database migrations,
FFmpeg and FFprobe. It verifies the frozen app with a temporary database and
without development tools on PATH before publishing to `deployment-package/windows`.
Copy that entire folder to a Windows 10/11 PC of the same CPU architecture and
run `MediaCleaner.exe`. The interface opens in the default browser. Keep its
console open; use the interface's exit action or Ctrl+C to stop the server.
Python and Node.js are not needed on the destination machine. ExifTool remains
optional and is not bundled. The output is unsigned, and clean-machine validation
and media-tool licensing review are still required before a public release.
The output includes a README, build information and available dependency notices.
Builds are local and require network access for dependencies and missing tools.

## Native installer plan

No Tauri shell or installer is claimed in Phase 1. The current development application runs a loopback Python backend serving the built React frontend.

The planned release shell is Tauri 2. It must spawn a bundled, per-platform Python sidecar, pass an ephemeral session token and selected loopback port, wait for readiness, load only that origin, and terminate/join the process on window close. Do not enable arbitrary shell access from the renderer. A packaging spike must verify sidecar process-tree shutdown and app-data permissions on every supported OS.

For packaged builds, use a per-platform PyInstaller (or equivalent validated Python bundling) build to include Python, Pillow/HEIF libraries and backend modules plus Alembic migrations, with separately licensed FFmpeg/FFprobe and ExifTool resources. Users must not need to install Python manually in release builds. Sign and notarize macOS arm64/x64 bundles, sign Windows installers, and build/test Linux packages against supported glibc versions. Codec licenses, executable signatures, updates, native Trash behavior, external drives and uninstall retention need release validation.

The supplied scripts are development installation, not a claim that the desktop packaging acceptance criteria are met.
