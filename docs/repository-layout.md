# Repository boundaries

`apps/desktop` contains the original current desktop app. Its backend and frontend are common to macOS, Windows and Linux. OS-specific additions belong in `apps/desktop/platforms/<os>`; desktop bundle configuration belongs in its packaging area. The Windows PowerShell scripts have moved to `platforms/windows`, while shared POSIX scripts remain in `apps/desktop/scripts`.

`apps/android` is reserved for Android source, native media access and Android builds. It currently contains boundary documentation, not a generated Android application. Choosing an Android UI/runtime and implementing native adapters are separate work.

`shared/contracts/src/api.ts` contains the common transport data types. The desktop UI's existing type module re-exports these definitions, so current imports keep working while the definitions have a single source. Desktop request validation, SQL persistence, native file access, media tools and UI remain in the desktop application; they are not claimed to run on Android. Additional truly shared code or language-neutral schemas should be introduced here when needed by an actual second consumer.

Root `scripts` holds compatibility entry points and local toolchain helpers. Existing `run.sh`, setup/check commands, and smoke-test commands still work by delegating into the desktop app. The local `.venv-phase1` and `.tools` stay at the root and remain ignored. After pulling this reorganization, rerun setup to refresh the editable backend's location; dependencies are still pinned in the desktop app's lockfiles.

Project-wide documentation remains under `docs`. Historical PhotoFold code remains archived under `legacy`. App data, folder-local scan caches and quarantined media are runtime data and are not relocated by this source-tree change. Generated Android SDK configuration, caches, packages and signing keys are ignored; Android source/build manifests and wrapper files should be tracked when added.

Validation on this workspace covers macOS Apple Silicon desktop tests, production build, root launchers, wheel packaging, and synthetic browser flow. Windows launchers and installers still require Windows validation; this reorganization does not create a Windows installer or Android APK.
