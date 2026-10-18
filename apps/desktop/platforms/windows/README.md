# Windows-specific desktop files

`setup.ps1` and `run.ps1` contain Windows development setup and launch behavior. From the repository root, the numbered Windows workflow is `scripts/windows/1-setup.ps1`, `2-build.ps1`, and `3-run.ps1`; `4-create-deploy-package.ps1` creates a portable deployment folder.

The desktop backend and frontend are shared with macOS/Linux. Future installer configuration, signing integration and Windows-only adapters belong here (or in the desktop packaging directory when used by the packaging system). The portable package bundles the app and runtime dependencies, but is not a Windows installer. Windows execution, native Trash behavior, external drives and signing still require validation on a Windows machine.
