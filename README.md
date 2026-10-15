# Media Cleaner · Similar photos, videos and animations

A local-first media inventory, exact and similar-media reviewer, and recoverable cleanup workspace. React + TypeScript + Vite + Tailwind + TanStack Query, backed by Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, and SQLite WAL.

**Similarity now covers supported still photos, camera RAW, videos and animated images.** Images use versioned pHash/dHash; videos and animations use multiple time-spaced frame comparisons. Approximate groups are `SIMILAR_CONTENT` and require manual review. Only complete SHA-256 equality is `EXACT_DUPLICATE`. Unsupported decoders are reported rather than silently skipped. Audio is not compared, and arbitrary trims/crops/partial clips and Tauri installers remain later work. See the [media-similarity implementation and limits](docs/phase-3.md). The earlier PhotoFold app remains archived in `legacy/`.

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

Setup installs the pinned Python dependencies, the editable backend, frontend dependencies from package-lock.json, a production frontend build, and setup-time FFmpeg/FFprobe installation when missing. For frontend development, run the backend in one terminal and `npm run dev --prefix frontend` in another; visit the Vite URL and paste the backend's launch token. Vite proxies `/api` to port 8765. VS Code tasks and pytest settings are included.

FFmpeg/FFprobe are installed during setup or can be provided on PATH. ExifTool is optional for richer metadata. Scanning never downloads tools. See [dependencies](docs/dependencies.md). Missing tools and skipped comparisons are shown in Settings and the scanner’s paginated warnings list. Exact hashing works without them. Native folder dialogs use macOS AppleScript, Windows FolderBrowserDialog, or Linux Zenity/KDialog; paste paths when a dialog is unavailable.

## Use

1. In **Scanner**, add one or more folders (including mounted external/network drives), choose Similar photos, videos & animations (default), or an exact-only all-media/image/video mode, and set exclusions. Similar sensitivity can be strict, balanced, or broad. Analysis only reads media.
2. Watch file/byte progress, current-file activity, and exact/similar groups as they are found on **Scanner**. Refreshing reconnects to the same running scan. Completed files are saved automatically; after a backend restart, choose **Resume** to continue from those checkpoints. Pause and cancel are also available. See [live progress and recovery](docs/scan-progress.md).
3. In **Duplicate review**, choose a scan and inspect side-by-side previews and SHA-256, photo-hash or time-spaced frame evidence. Use **Compare videos together** in Scanner or Duplicate review to open every video in a group, then **Play all from start**, **Pause all**, or **Reset all**. Comparison starts muted; unmute individual players to check audio before deciding what to remove. Buffering may affect playback timing. Every similar-media group starts with all files kept; uncheck unwanted versions manually. A file can appear in both an exact group and a similar group. “Keep” is checked for the likely original when exactly one filename lacks copy markers. Ambiguous groups keep every file until you select manually. All protected files remain checked.
4. Groups on **Scanner**, during and after scanning, show **Select for deletion** checkboxes and a per-group **Delete selected** button. **Duplicate review** uses **Keep this file** checkboxes: uncheck unwanted files, then choose **Delete unchecked**. Video cards show generated thumbnails before playback. This creates a dry run for the unchecked files **on the current member page**. Large groups are paginated, 50 members per page.
5. Choose OS Trash/Recycle Bin (default) or same-volume quarantine. Review the source paths, retained copies and size, check the explicit confirmation box, then confirm cleanup. No permanent deletion endpoint exists. Trash failure never silently falls back to quarantine or deletion.
6. **Cleanup** keeps results and recovery records. Restore quarantine here; restore Trash items through the operating system. Quarantine restore refuses to overwrite an occupied original path. Rescan restored files to include them in a new inventory.

Cleanup is conservative: files and retained copies must still match their recorded device, inode, size, modification and change timestamps. Both contents are freshly SHA-256 verified against their own scan snapshots before execution, with checks repeated before each move. RAW originals, configured protected directories, and potential same-stem photo/video companions are blocked from cleanup. That companion rule is a safety heuristic, not verified Live Photo recognition.

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
- `backend/migrations/`: versioned Alembic migrations, automatically applied at startup.
- `backend/tests/`: unit, API, persistence, worker and cleanup safety tests.
- `frontend/src/`: real React pages, shared components, typed API client and SSE hook.
- `scripts/`: setup, launch, verification and test tooling.
- `desktop/`: release strategy documentation; no Phase 5 desktop shell is claimed.
- `legacy/`: preserved earlier PhotoFold implementation and tests, isolated from the Phase 1 entry point.

Database, API token, and rotating diagnostic logs default to platform application data (`~/Library/Application Support/MediaCleaner` on macOS, user local application data on Windows, and XDG data home on Linux). These should stay on local storage, outside scanned collections. Quarantine deliberately lives on the source volume at `.media-cleaner-quarantine/<operation>/<unique-id>/<filename>` so moves do not copy large videos across drives.

## Current limits and next phase

The app compares binary equality, photo appearance, and sampled video/animation sequences; it also decodes RAW previews with rawpy/LibRaw. Actual codec/camera support varies. Missing, corrupt or unsupported inputs retain exact-match coverage and appear in scanner warnings. Video matching does not compare audio or every frame, so manual playback review is essential. Crops, trims, partial overlap, semantic matching and audio fingerprints are not implemented. Static/low-detail clips and long or untimed animations may be omitted from approximate analysis. No verified Live Photo pairing, scheduling, packaged Tauri runtime, stable cross-platform hardware UUID or 100k-file performance guarantee is claimed. Versioned fingerprints are cached for unchanged files; normal operation is offline after setup.

Next: broader corpus calibration and **Phase 4** partial/advanced similarity and audio corroboration. See [architecture](docs/architecture.md), [algorithms](docs/algorithms.md), [API](docs/api.md), [database](docs/database.md), [security](docs/security.md), and [Phase 1 status](docs/phase-1.md).
