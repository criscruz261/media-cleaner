# macOS desktop workflow

Run from the repository root on macOS:

1. `./scripts/macOS/1-setup.sh` — install Python/frontend dependencies, packaging tools, FFmpeg and FFprobe.
2. `./scripts/macOS/2-build.sh` — build the frontend and backend wheel.
3. `./scripts/macOS/3-run.sh` — run locally; open the printed launch link.
4. `./scripts/macOS/4-create-deploy-package.sh` — rebuild and create `deployment-package/macOS/MediaCleaner.app`.

Build each component independently with `2.a-build-frontend.sh` or
`2.b-build-backend.sh`. Setup requires Python 3.12+ and Node 22.12+ with npm
already installed. Setup finds compatible project-local, versioned, Homebrew,
and python.org Python installations automatically. Set `PYTHON_BIN` to select
a specific Python executable. Xcode command line tools
are required for macOS code signing during packaging. Dependency installation
requires network access. Setup does not build the application.

Packaging includes the Python runtime, backend, built frontend, migrations,
FFmpeg and FFprobe, then verifies the frozen app's UI, authenticated API,
database initialization and media tools outside the repository before publishing.
The backend wheel is an independent build artifact in
`apps/desktop/backend/dist`; packaging freezes the installed backend directly.

Copy the `.app` to a Mac with the same CPU architecture and the same or a newer
macOS version. No Python or Node installation is needed there. The app opens
in the default browser; use Exit app to stop it. Build separately for Intel and
Apple Silicon. The bundle is ad-hoc signed; public distribution still requires
Developer ID signing, notarization, and clean-machine validation. See the
packaged README for transfer and app-data details.
