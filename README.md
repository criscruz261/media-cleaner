# Media Cleaner · Similar photos, videos and animations

A local-first media inventory, exact and similar-media reviewer, and recoverable cleanup workspace. React + TypeScript + Vite + Tailwind + TanStack Query, backed by Python 3.12+, FastAPI, Pydantic, SQLAlchemy, Alembic, and SQLite WAL.

**Similarity now covers supported still photos, camera RAW, videos and animated images.** Images use versioned pHash/dHash; videos and animations use multiple time-spaced frame comparisons. Approximate groups are `SIMILAR_CONTENT` and require manual review. Only complete SHA-256 equality is `EXACT_DUPLICATE`. Unsupported decoders are reported rather than silently skipped. Audio is not compared, and arbitrary trims/crops/partial clips and Tauri installers remain later work. See the [media-similarity implementation and limits](docs/phase-3.md). The earlier PhotoFold app remains archived in `legacy/`.

## Run on this workspace

The project-local Python environment and production frontend have been prepared:

```sh
./run.sh
```

After changing the desktop code, stop the running app, rebuild, then launch it again:

```sh
./build-desktop.sh
./run.sh
```

The build script refreshes frontend dependencies from the lockfile and compiles the production UI served by `run.sh`. Python source changes are loaded when the backend restarts. This does not create a packaged desktop installer; rerun `./scripts/setup.sh` when Python dependencies change.

Open the launch link printed in the terminal. It includes a local access token in the URL fragment, which is removed after connecting and exchanged for an HttpOnly, SameSite cookie. Do not share the launch link. Stop with Ctrl+C. Use `./run.sh --port 9000` or `./run.sh --data-dir /absolute/local/app-data` to override defaults.

To clean up multiple groups on desktop, make your selections in **Matches found so far** or **Review**, then choose **Delete selected across groups**. The combined preview includes reviewed groups across every page of the selected scan and requires confirmation before moving files.

## Android build

Numbered setup, build, device launch, and deployment packaging scripts are in
`scripts/android/`. See the [Android script workflow](apps/android/README.md#numbered-scripts).

A standalone Android 11+ app is available under [apps/android](apps/android/README.md), with native media access, offline scanning, thumbnails, video comparison, saved checkpoints and system-confirmed Trash/restore. On a fresh macOS Apple Silicon clone, install Python 3.12+ and curl, then run `./setup-android.sh` and `./build-android.sh`. Setup keeps its tools in ignored `.tools/android`; the build finds them automatically. Other hosts can configure JDK 21 and Android SDK 35 manually before running the build script. The installable debug APK is generated at `apps/android/app/build/outputs/apk/debug/app-debug.apk`. This is a testing build, not a Play Store release.

## Fresh development setup

Install **Python 3.12+** and **Node 22.12+** (Node 22 LTS is the tested development runtime). Network access is needed for installation, not for normal operation.

macOS / Linux:

```sh
# If python3 is older, set PYTHON_BIN=/absolute/path/to/python3.12
./scripts/setup.sh
./run.sh
```

For the numbered macOS workflow, use `./scripts/macOS/1-setup.sh`,
`./scripts/macOS/2-build.sh`, then `./scripts/macOS/3-run.sh`.
`./scripts/macOS/4-create-deploy-package.sh` builds a self-contained
`deployment-package/macOS/MediaCleaner.app` for another Mac of the same CPU
architecture with the same or a newer macOS version. See the
[macOS build and packaging guide](apps/desktop/platforms/macos/README.md).

Windows PowerShell:

```powershell
# Optionally set $env:PYTHON_BIN to your Python 3.12+ executable
./scripts/windows/1-setup.ps1
./scripts/windows/2-build.ps1
./scripts/windows/3-run.ps1
```

Build the frontend or backend wheel independently with
`./scripts/windows/2.a-build-frontend.ps1` or
`./scripts/windows/2.b-build-backend.ps1`. To create the portable Windows
deployment folder, run `./scripts/windows/4-create-deploy-package.ps1`.
`2-run.ps1` and `3-create-deploy-package.ps1` remain available as compatibility
aliases.

Windows setup detects Python 3.12+ and Node 22.12+ and installs missing prerequisites using `winget` (Microsoft App Installer). Installer prompts may request elevation. If winget cannot provide a usable Node.js installation, setup downloads the official Node.js 22 Windows ZIP, verifies its SHA-256 checksum, and keeps it in ignored `.tools/node` without administrator access. Setup reuses this runtime on later runs. It refreshes PATH for the current session before creating the environment and building the app. If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal first. An explicit `PYTHON_BIN` must point to a working Python 3.12+ executable.

Setup installs the pinned Python dependencies, the editable backend, frontend dependencies from package-lock.json, a production frontend build, and setup-time FFmpeg/FFprobe installation when missing. For frontend development, run the backend in one terminal and `npm run dev --prefix apps/desktop/frontend` in another; visit the Vite URL and paste the backend's launch token. Vite proxies `/api` to port 8765. VS Code tasks and pytest settings are included.

FFmpeg/FFprobe are installed during setup or can be provided on PATH. ExifTool is optional for richer metadata. Scanning never downloads tools. See [dependencies](docs/dependencies.md). Missing tools and skipped comparisons are shown in Settings and the scanner’s paginated warnings list. Exact hashing works without them. Native folder dialogs use macOS AppleScript, Windows FolderBrowserDialog, or Linux Zenity/KDialog; paste paths when a dialog is unavailable.

## Scan and Continue Scan

Choose a mode in the dropdown to update the button label, then press the main
button to start. Selecting a dropdown item does not start scanning.

Android and desktop offer a **Scan** button with a dropdown for **Continue Scan**.
Scan recomputes hashes and visual analysis, bypassing saved analysis and checkpoints.
Continue Scan resumes a paused/interrupted checkpoint, or reuses valid analysis
from a completed scan. Desktop continuation after completion uses the current
folder and scan options; Android continues the saved media selection.
Desktop bypasses database and `.media-cleaner-cache` analysis for fresh scans.
New results are cached normally. Source media and cleanup history are preserved.

## Use

1. In **Scanner**, add one or more folders (including mounted external/network drives), choose Similar photos, videos & animations (default), or an exact-only all-media/image/video mode, and set exclusions. Similar sensitivity can be strict, balanced, or broad. Analysis reads media and writes checkpoints to `.media-cleaner-cache` inside each selected root. It does not modify media files.
2. Watch file/byte progress, current-file activity, and exact/similar groups as they are found on **Scanner**. Refreshing reconnects to the same running scan. Completed files and explicit selections are saved automatically to the app database and a hidden `.media-cleaner-cache` in each selected folder; after a backend restart, choose **Continue Scan** to continue from those checkpoints. Pause and cancel are also available. See [live progress and recovery](docs/scan-progress.md).
3. In **Duplicate review**, choose a scan and inspect side-by-side previews and SHA-256, photo-hash or time-spaced frame evidence. Use **Compare videos together** in Scanner or Duplicate review to open every video in a group, then **Play all from start**, **Pause all**, or **Reset all**. Comparison starts muted; unmute individual players to check audio before deciding what to remove. Buffering may affect playback timing. The comparison window has **Select for deletion** checkboxes; choices are saved to the group. Close the window to preview and confirm cleanup. Every similar-media group starts with all files kept; select unwanted versions for deletion. A file can appear in both an exact group and a similar group. Exact groups retain one suggested keeper, preferring the original filename when identifiable, and pre-select the remaining copies for deletion. Protected files stay kept.
4. Groups on **Scanner**, during and after scanning, show **Select for deletion** checkboxes and a per-group **Delete selected** button. **Duplicate review** uses the same **Select for deletion** checkboxes: check unwanted files, then choose **Delete selected**. Changes save automatically; no separate mark-reviewed action is needed. Batch cleanup includes pre-selected exact copies and your selections in similar groups matching the current filter across every page. Video cards show generated thumbnails before playback. This creates a dry run for the selected files **across every member page in the group**. Large groups are paginated, 50 members per page.
5. Choose OS Trash/Recycle Bin (default) or same-volume quarantine. Review the source paths, retained copies and size, check the explicit confirmation box, then confirm cleanup. No permanent deletion endpoint exists. Trash failure never silently falls back to quarantine or deletion.
6. **Cleanup** keeps results and recovery records. Restore quarantine here; restore Trash items through the operating system. Quarantine restore refuses to overwrite an occupied original path. Rescan restored files to include them in a new inventory.

Cleanup is conservative: files and retained copies must still match their recorded device, inode, size, modification and change timestamps. Both contents are freshly SHA-256 verified against their own scan snapshots before execution, with checks repeated before each move. RAW originals, configured protected directories, and potential same-stem photo/video companions are blocked from cleanup. That companion rule is a safety heuristic, not verified Live Photo recognition.

## Validation

```sh
./scripts/check.sh
# Or independently:
cd apps/desktop/backend
../../../.venv-phase1/bin/python -m pytest
# From the project root:
npm test --prefix apps/desktop/frontend
npm run build --prefix apps/desktop/frontend
```

All cleanup tests use temporary synthetic media. The local browser smoke script additionally exercises the real UI and real backend against temporary media; see [testing](docs/testing.md). Windows and Linux scripts are supplied but have not been run on those operating systems in this workspace. No 100,000-file benchmark or installer certification is claimed.

## Layout

```text
apps/
  desktop/                 Existing macOS/Windows/Linux app
    backend/               Python service, migrations and tests
    frontend/              React desktop interface and tests
    scripts/               Desktop development and verification tools
    platforms/
      macos/
      windows/             Windows-specific PowerShell setup and launch
      linux/
    packaging/             Desktop installer strategy
  android/                 Standalone native Android app and APK build
shared/
  contracts/src/api.ts     Common data types consumed by the desktop UI
  matching/                Platform-independent Java matching core for Android
scripts/                   Root compatibility launchers and toolchain helpers
docs/                      Project-wide documentation
legacy/                    Archived earlier PhotoFold implementation
```

Use [apps/desktop](apps/desktop/README.md) for the current app, [apps/android](apps/android/README.md) for Android-specific work, and [shared](shared/README.md) for cross-application definitions. Windows will use the same desktop backend/frontend with Windows-specific adapters and packaging. The Android app now builds separately; desktop installers remain future work.

Root `./run.sh`, `./scripts/setup.sh`, `./scripts/check.sh`, and PowerShell entry points continue to work. Existing checkouts should rerun setup once after this move to refresh the editable Python installation. See [repository boundaries](docs/repository-layout.md).

Folder-local analysis checkpoints live under `<selected folder>/.media-cleaner-cache/`. Rescanning the same folder can reuse them even with a fresh app database. Changed file identities are reprocessed. Unwritable folders fall back to the app database with a scanner warning. The cache is not a backup of media or cleanup history.

Database, API token, and rotating diagnostic logs default to platform application data (`~/Library/Application Support/MediaCleaner` on macOS, user local application data on Windows, and XDG data home on Linux). These should stay on local storage, outside scanned collections. Quarantine deliberately lives on the source volume at `.media-cleaner-quarantine/<operation>/<unique-id>/<filename>` so moves do not copy large videos across drives.

## Current limits and next phase

The app compares binary equality, photo appearance, and sampled video/animation sequences; it also decodes RAW previews with rawpy/LibRaw. Actual codec/camera support varies. Missing, corrupt or unsupported inputs retain exact-match coverage and appear in scanner warnings. Video matching does not compare audio or every frame, so manual playback review is essential. Crops, trims, partial overlap, semantic matching and audio fingerprints are not implemented. Static/low-detail clips and long or untimed animations may be omitted from approximate analysis. No verified Live Photo pairing, scheduling, packaged Tauri runtime, stable cross-platform hardware UUID or 100k-file performance guarantee is claimed. Versioned fingerprints are cached for unchanged files; normal operation is offline after setup.

Next: broader corpus calibration and **Phase 4** partial/advanced similarity and audio corroboration. See [architecture](docs/architecture.md), [algorithms](docs/algorithms.md), [API](docs/api.md), [database](docs/database.md), [security](docs/security.md), and [Phase 1 status](docs/phase-1.md).

### Matching controls

Scanner offers a **Strict → Balanced → Loose → Very loose → Extra loose → Maximum** sensitivity slider. Balanced is
the default; Loose returns more candidates that need review. Exact SHA-256
duplicate detection is unchanged. The landscape examples illustrate small and
larger edits; they are not a promise that a specific pair will match.

**Video samples** selects 6–24 evenly spaced frames per video (default 9). More
frames cover more of the timeline and take longer; audio and unsampled moments
can still differ. Desktop applies this count to animations too. Cached frame
analysis is reused only when its sample count matches. Continue Scan uses the
saved settings for unfinished scans; Scan starts fresh with the chosen settings.
Android places these controls under **1. Scan setup → Matching options**.

The sensitivity section is centered. Very loose, Extra loose, and Maximum widen
perceptual hash and duration tolerances progressively. Maximum can include
unrelated candidates; inspect groups before deleting. The two-photo preview
uses progressively stronger display color edits for the added levels.

### Subject and scene variation

Similarity scans now use a bundled local image model alongside pHash/dHash.
Maximum can find broader subject/scene resemblance across movement, changed
poses, camera angles and backgrounds. Region features help when objects are
missing or obscured. Lower sensitivity levels require closer agreement; Strict
retains whole-image hash matching. This is visual similarity, not identity
verification, and every approximate match still needs review. Video samples use
the same features. Old descriptors are re-analyzed once for the new model.
See [subject matching](docs/subject-matching.md) for model provenance and thresholds.
