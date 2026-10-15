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

Similar-photo browser validation: start the fixture server with `--similar`, then run the same browser script. This additionally checks all-kept defaults, manual unchecking, pHash/dHash evidence, the approximate-content warning, quarantine and restore. Backend tests cover cross-format/resize/brightness changes, orientation, unsupported content, cache invalidation, indexed-search equivalence, complete-link chain rejection, exact-video support and scoped manual cleanup.

All-media browser fixture: start `scripts/smoke-server.py /tmp/media-cleaner-smoke.json --video` and run the same browser script. This verifies generated video similarity, real browser playback, sequence evidence, manual unchecking, confirmation, quarantine and restore. Codec/animation/RAW regression tests use actual local decoders and synthetic inputs; FFmpeg-dependent tests are explicitly skipped if tools are missing on another environment.

Live progress/recovery: add `--similar --live` to the fixture server command. It holds one temporary file pending while the other files publish exact and similar groups. Chrome checks live previews, reloads the page and verifies the same scan ID, clears browser storage and verifies server-side active-job recovery, then releases the pending file and completes review/confirmation/quarantine/restore. Backend regression tests check partial results, saved counters, blocked provisional review, and pause/resume without rehashing completed files. Browser storage tests cover draft/selection recovery and corrupt storage fallback.

Video comparison controls are covered by a frontend test that loads multiple member pages, waits for playable media, starts every player from zero, pauses/resets together, and closes with Escape. The `--video` Chrome fixture also verifies both videos actually advance together and shared pause/reset work before the existing review and cleanup checks.

Thumbnail coverage verifies JPEG dimensions, unchanged-source cache reuse, and rejection after source changes. Completed Scanner coverage verifies visible keep checkboxes, group-scoped dry-run creation and no execution without confirmation. The Chrome video fixture checks real FFmpeg-generated posters and Scanner controls before the review/cleanup flow.
