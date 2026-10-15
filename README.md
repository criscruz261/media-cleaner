# Media Cleaner · Phase 1

A local-first media inventory, exact duplicate reviewer, and recoverable cleanup workspace. React + TypeScript + Vite + Tailwind + TanStack Query, backed by Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, and SQLite WAL.

**Phase 1 is implemented. Advanced image similarity, re-encoded video matching, and Tauri installers are later phases.** Only complete SHA-256 equality is classified as `EXACT_DUPLICATE` in this version. The earlier PhotoFold app is preserved in `legacy/`; it is not launched by the new scripts and its old permanent-delete workflow is not part of the new application.

## Run on this workspace

The project-local Python environment and production frontend have been prepared:

```sh
./run.sh
```

Open the launch link printed in the terminal. It includes a local access token in the URL fragment, which is removed after connecting and exchanged for an HttpOnly, SameSite cookie. Do not share the launch link. Stop with Ctrl+C. Use `./run.sh --port 9000` or `./run.sh --data-dir /absolute/local/app-data` to override defaults.

## Fresh development setup

Install **Python 3.12+** and **Node 22.12+** (Node 22 LTS is the tested development runtime). Network access is needed for installation, not for normal operation.

macOS / Linux:

```sh
# If python3 is older, set PYTHON_BIN=/absolute/path/to/python3.12
./scripts/setup.sh
./run.sh
```

Windows PowerShell:

```powershell
# Optionally set $env:PYTHON_BIN to your Python 3.12+ executable
./scripts/setup.ps1
./scripts/run.ps1
```

Setup installs the pinned Python dependencies, the editable backend, frontend dependencies from package-lock.json, and a production frontend build. For frontend development, run the backend in one terminal and `npm run dev --prefix frontend` in another; visit the Vite URL and paste the backend's launch token. Vite proxies `/api` to port 8765. VS Code tasks and pytest settings are included.

Optional metadata tools: install FFmpeg (including FFprobe) and ExifTool on PATH. See [dependencies](docs/dependencies.md). Missing tools are shown in Settings and per-file metadata warnings. Exact hashing works without them. Native folder dialogs use macOS AppleScript, Windows FolderBrowserDialog, or Linux Zenity/KDialog; paste paths when a dialog is unavailable.

## Use

1. In **Scanner**, add one or more folders (including mounted external/network drives), choose all media/images/videos, and set exclusions. Analysis only reads media.
2. Pause, cancel, or resume the current scan. Progress uses SSE, with polling reconnection. History and unchanged-file hash/metadata caches survive restart.
3. In **Duplicate review**, choose a scan and inspect side-by-side previews and SHA-256 evidence. “Keep” is checked for the likely original when exactly one filename lacks copy markers. Ambiguous groups keep every file until you select manually. All protected files remain checked.
4. Uncheck unwanted files in a group and choose **Preview cleanup**. This creates a dry run for the unchecked files **on the current member page**. Large groups are paginated, 50 members per page.
5. Choose OS Trash/Recycle Bin (default) or same-volume quarantine. Review the source paths, retained copies and size, check the explicit confirmation box, then confirm cleanup. No permanent deletion endpoint exists. Trash failure never silently falls back to quarantine or deletion.
6. **Cleanup** keeps results and recovery records. Restore quarantine here; restore Trash items through the operating system. Quarantine restore refuses to overwrite an occupied original path. Rescan restored files to include them in a new inventory.

Cleanup is conservative: files and retained copies must still match their recorded device, inode, size, modification and change timestamps. Both contents are freshly SHA-256 verified before execution, with checks repeated before each move. RAW originals, configured protected directories, and potential same-stem photo/video companions are blocked from cleanup in Phase 1. That companion rule is a safety heuristic, not verified Live Photo recognition.

## Validation

```sh
./scripts/check.sh
# Or independently:
cd backend
../.venv-phase1/bin/python -m pytest
# From the project root:
npm test --prefix frontend
npm run build --prefix frontend
```

All cleanup tests use temporary synthetic media. The local browser smoke script additionally exercises the real UI and real backend against temporary media; see [testing](docs/testing.md). Windows and Linux scripts are supplied but have not been run on those operating systems in this workspace. No 100,000-file benchmark or installer certification is claimed.

## Layout

- `backend/app/`: API, core filesystem/security, discovery, metadata, hashing, grouping, retention, cleanup, database and managed workers.
- `backend/migrations/`: immutable initial Alembic migration, automatically applied at startup.
- `backend/tests/`: unit, API, persistence, worker and cleanup safety tests.
- `frontend/src/`: real React pages, shared components, typed API client and SSE hook.
- `scripts/`: setup, launch, verification and test tooling.
- `desktop/`: release strategy documentation; no Phase 5 desktop shell is claimed.
- `legacy/`: preserved earlier PhotoFold implementation and tests, isolated from the Phase 1 entry point.

Database, API token, and rotating diagnostic logs default to platform application data (`~/Library/Application Support/MediaCleaner` on macOS, user local application data on Windows, and XDG data home on Linux). These should stay on local storage, outside scanned collections. Quarantine deliberately lives on the source volume at `.media-cleaner-quarantine/<operation>/<unique-id>/<filename>` so moves do not copy large videos across drives.

## Current limits and next phase

Phase 1 detects binary equality across supported extensions, not visually similar images or re-encoded videos. Metadata and preview support depends on installed decoders; unsupported codecs still participate in exact matching. FFprobe/ExifTool are optional at startup but required for comprehensive video/RAW metadata. No RAW rendering, verified Live Photo pairing, embeddings, partial-video matching, scheduling, database relocation UI, or packaged Tauri runtime is presented as complete. Hardware volume identity is currently session-local device/mount identity, not a persistent cross-platform hardware UUID. Fingerprint tables reserve versioned storage for later engines.

Next: **Phase 2**, indexed pHash/dHash image comparison with calibrated, explainable classifications and tests. See [architecture](docs/architecture.md), [algorithms](docs/algorithms.md), [API](docs/api.md), [database](docs/database.md), [security](docs/security.md), and [Phase 1 status](docs/phase-1.md).
