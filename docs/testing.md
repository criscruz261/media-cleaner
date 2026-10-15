# Testing

Run `scripts/check.sh` with Python/Node available (or invoke pytest, Vitest and the Vite build separately as documented in README). Tests create synthetic media in temporary directories. They never target the user's collections.

Backend coverage includes streamed SHA-256, content changes, multi-root recursive discovery, case-insensitive extensions, hidden/excluded paths, symlink loops/replacements, hard-link deduplication, corrupt media, metadata/cache reuse, SQLite WAL/foreign keys/migrations, persisted history, real worker pause/resume/cancel, disconnected roots, startup interruption, original-name/manual retention, RAW/companion protection, image/range-video previews, local authentication/origins, diagnostic download, dry-run/confirmation, expired plans, missing keepers, Trash errors, quarantine/restore and no-overwrite recovery.

Frontend Vitest/React Testing Library checks explicit cleanup confirmation, selected/retained paths, video controls and fallback, and multi-root scanner request payloads. Test HTTP mocks are test fixtures only; the shipped UI uses the real backend.

A real Chrome smoke test is also provided. Install frontend development dependencies, build, then run two terminals from the repository root:

```sh
.venv-phase1/bin/python scripts/smoke-server.py /tmp/media-cleaner-smoke.json
```

```sh
node scripts/browser-smoke.mjs /tmp/media-cleaner-smoke.json
```

The server fixture creates only temporary synthetic images and uses loopback port 18765. Stop it with Ctrl+C afterward. The browser script defaults to installed macOS Chrome; set `CHROME_PATH` for another OS/executable. It launches an isolated temporary headless browser profile, authenticates with the fixture token, starts a real scan, checks original preselection, previews quarantine, verifies confirmation gating, executes quarantine, and restores. It records desktop/mobile screenshots in ignored `.tools/smoke-artifacts`. No production user media is passed to this test. Do not substitute real collection paths into test fixtures.

Current validation is on macOS Apple Silicon. Windows/Linux, unusual external/network filesystems, native Trash across devices, all codec variants and 100,000-file performance require platform-specific validation before release. Tests simulate permission failures through the platform adapter rather than relying on administrator-dependent file mode behavior. FastAPI/Starlette currently emit a test-client httpx deprecation warning; test results pass, and the warning is recorded rather than hidden.
