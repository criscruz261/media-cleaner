# Shared files

Cross-application definitions belong here. Platform launchers, media access, filesystem operations, and native build resources belong in their application directories.

- `contracts/src/api.ts`: transport/domain data types currently consumed by the desktop UI through its local type re-export.

Android is not implemented yet. Sharing these definitions does not make the Python backend or React desktop UI Android-compatible. Add shared algorithms, resources or test vectors here when there is a concrete consumer; keep platform dependencies out of shared packages.

Project-wide documentation lives in the root `docs/` directory, and developer toolchain helpers remain in root `scripts/`.
