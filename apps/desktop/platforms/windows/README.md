# Windows-specific desktop files

`setup.ps1` and `run.ps1` contain Windows development setup and launch behavior. Root `scripts/windows/1-setup.ps1` and `scripts/windows/2-run.ps1` delegate here.

The desktop backend and frontend are shared with macOS/Linux. Future installer configuration, signing integration and Windows-only adapters belong here (or in the desktop packaging directory when used by the packaging system). Windows execution, native Trash behavior, external drives and signing have not been validated on a Windows machine in this workspace. No Windows installer is supplied yet.
