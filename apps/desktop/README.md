# Desktop app

The existing Media Cleaner application for macOS, with Windows and Linux development launch scripts supplied. The shared desktop implementation stays together; Windows does not need a separate copy of the backend or UI.

- `backend/`: Python/FastAPI service, scanning/matching, SQLite, cleanup, migrations and tests.
- `frontend/`: React desktop UI and tests. Common transport types come from `shared/contracts` at the repository root.
- `scripts/`: desktop setup, launch, checks, media-tool installation and synthetic browser tests.
- `platforms/windows/`: PowerShell development setup/launch and future Windows integration.
- `platforms/macos/`, `platforms/linux/`: platform-specific integration and release notes.
- `packaging/`: planned desktop packaging; no installer is implemented yet.

From the repository root use `./run.sh`, `./scripts/setup.sh`, and `./scripts/check.sh`. On Windows use `./scripts/setup.ps1` and `./scripts/run.ps1`. These compatibility entry points delegate into this directory. Local Python environments and downloaded toolchains stay at the repository root.

Keep common desktop behavior in the backend/frontend. Put OS-specific additions under the corresponding platform directory instead of copying the application. OS adapters already supplied by Python libraries remain dependencies of the desktop backend.

Open a thumbnail or **Open group preview** to browse the entire group, including files on other result pages. Use **Previous/Next** (or arrow keys), zoom controls, **Fit to screen**, and **Select for deletion** without closing the preview. Escape closes it. The preview fits the current window; zoomed photos can be dragged to pan. Drag the sidebar’s right edge to resize it, or use its collapse/expand button. Width and collapsed state persist locally; the resize handle also supports arrow keys, Home and End.
