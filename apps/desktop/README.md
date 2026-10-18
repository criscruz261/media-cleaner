# Desktop app

The existing Media Cleaner application for macOS, with Windows and Linux development launch scripts supplied. The shared desktop implementation stays together; Windows does not need a separate copy of the backend or UI.

- `backend/`: Python/FastAPI service, scanning/matching, SQLite, cleanup, migrations and tests.
- `frontend/`: React desktop UI and tests. Common transport types come from `shared/contracts` at the repository root.
- `scripts/`: desktop setup, launch, checks, media-tool installation and synthetic browser tests.
- `platforms/windows/`: PowerShell development setup/launch and future Windows integration.
- `platforms/macos/`, `platforms/linux/`: platform-specific integration and release notes.
- `packaging/`: planned desktop packaging; no installer is implemented yet.

From the repository root use `./run.sh`, `./scripts/setup.sh`, and `./scripts/check.sh`. On Windows, use `./scripts/windows/1-setup.ps1`, `./scripts/windows/2-build.ps1`, and `./scripts/windows/3-run.ps1`; `./scripts/windows/4-create-deploy-package.ps1` builds a portable deployment folder. Local Python environments and downloaded toolchains stay at the repository root.

Keep common desktop behavior in the backend/frontend. Put OS-specific additions under the corresponding platform directory instead of copying the application. OS adapters already supplied by Python libraries remain dependencies of the desktop backend.

Open a thumbnail or **Open group preview** to browse the entire group, including files on other result pages. Use **Previous/Next** (or arrow keys), zoom controls, **Fit to screen**, and **Select for deletion** without closing the preview. Escape closes it. The preview fits the current window; zoomed photos can be dragged to pan. Drag the sidebar’s right edge to resize it, or use its collapse/expand button. Width and collapsed state persist locally; the resize handle also supports arrow keys, Home and End.

Scans always skip system Trash/Recycle Bin directories (`$RECYCLE.BIN`, `RECYCLER`, `RECYCLED`, `.Trash`, `.Trashes`, and `.Trash-<uid>`), app cache/quarantine directories, and zero-byte media files. These exclusions also apply when hidden-file scanning is enabled or a trash directory is entered directly. Start a new scan to apply these rules to existing results.

Live groups are listed in first-publication order, so new groups append after existing results instead of sorting by size or latest update. The scan status stays visible while scrolling and inside group previews. Open previews live independently of result cards; live updates or page changes preserve the current file and zoom. Existing groups may still gain members, and cleanup always revalidates saved choices before moving files.

Use **Pause & save checkpoint** in the pinned scan bar to wait until scanning has stopped and completed work is saved. **Resume from checkpoint** continues after rechecking files; unfinished work is processed again. **Shut down safely** asks for confirmation, saves the checkpoint, stops the backend started by `./run.sh`, and shows a safe-to-close page. Closing a browser tab alone leaves the backend running.

Group and batch deletion open an in-place review/confirmation dialog. Confirm the listed moves, review the outcome, and choose **Done** to continue on the same results page. **Cleanup** remains available for history and recovery.
