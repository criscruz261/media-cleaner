# API v1

All routes are under `/api/v1`. Authenticate with `Authorization: Bearer <launch token>` or the established session cookie. Cookie mutations require a matching local Origin. Responses use JSON; errors use `{error:{code,message,details?}}`. Pydantic validates request bodies and bounds lists. API JSON request bodies are capped at 1 MiB. Authenticated OpenAPI: `GET /openapi.json` (no CDN Swagger page).

| Method / path | Purpose |
| --- | --- |
| POST /session | Exchange Bearer launch token for HttpOnly session cookie |
| GET /health | Phase and installed media-tool availability |
| GET /dashboard | Latest-scan inventory, group counts and logical savings |
| POST /folders/choose | Explicitly open a platform-native directory dialog |
| POST /scans | Start `roots`, `mode` (similar/exact/images/videos), sensitivity (strict/balanced/broad), exclusions, hidden option |
| GET /scans | Paginated persisted scan history |
| GET /scans/active | Recover the active or most recent paused/interrupted job |
| GET /scans/{id} | Job state, saved file/byte counters, checkpoint timestamp and current-file activity |
| GET /scans/{id}/matches | Paginated live groups, exact/similar counts, provisional flag and checkpoint timestamp |
| POST /scans/{id}/pause | Request checkpoint pause |
| POST /scans/{id}/stop | Save completed checkpoints, wait for worker shutdown, and end the scan; saved results remain available |
| POST /scans/{id}/cancel | Request checkpoint cancellation |
| POST /scans/{id}/resume | Resume paused/interrupted/failed job when worker has stopped |
| GET /scans/{id}/selection-summary | Distinct selected/total ready files in visible groups; optional classification filter, across all pages |
| GET /scans/{id}/warnings | Paginated skipped-analysis and metadata warnings |
| GET /scans/{id}/events | SSE progress snapshots and heartbeat; closes at a terminal state |
| GET /volumes | Previously observed volumes; not an exhaustive OS volume picker |
| GET /files?scan_id=... | Paginated inventory; optional status filter |
| GET /files/{id} | Identity, status, metadata and warnings |
| GET /files/{id}/thumbnail | Small JPEG still/video poster; identity checked, bounded in-memory cache |
| GET /files/{id}/preview | Normalized image preview or range-capable original video |
| GET /groups?scan_id=... | Paginated unresolved exact/similar groups; optional classification filter and sort |
| GET /groups/{id} | Paginated current members and saved keep choices |
| POST /groups/{id}/review | Set `keep_ids` or partial `changes:{file_id:boolean}`; empty `keep_ids:[]` selects the entire group for deletion; protected assets must stay kept |
| POST /cleanup/plan | Dry run for `file_ids`, `group_id` (required for approximate groups), destination `trash` or `quarantine` |
| GET /cleanup/{id}/progress | Live persisted cleanup status, processed/moved/failed counts, bytes moved and current file; readable during execution |
| POST /cleanup/execute | `plan_id`, matching plan `token`, `confirmed:true` |
| GET /cleanup/history | Paginated plans, outcomes and recovery records |
| POST /cleanup/{id}/restore | `confirmed:true`; quarantine recovery only |
| GET /settings | Current validated preferences |
| PUT /settings | Save protection/exclusions, workers, theme and destination |
| GET /diagnostics | Download rotating local diagnostic log |

List responses are `{items,total}` with `offset`/`limit`, except the observed-volume list. Limit caps vary from 100 to 200 by resource. A scan root must be an existing directory. Multiple roots share one scan and physical-file deduplication. Live groups can gain members; review writes and confirmed cleanup are available during and after scanning. Only already processed, verified group members are eligible. Cleanup from a different scan is blocked while another scan is active. Approximate groups require a saved manual review and an explicit group-scoped plan. Protected choices cannot be unchecked. No arbitrary shell commands, arbitrary preview paths, arbitrary shell access or permanent-delete API is exposed.

The `similar` mode now compares still photos/RAW and video/animation sequences. Sequence evidence includes `media_kind:sequence`, sample counts, duration difference, algorithm version and limitations. It remains approximate and requires manual review; no audio equality is asserted.

`POST /api/v1/cleanup/plan-selected` takes `scan_id` and `destination` (`trash` or `quarantine`). It previews saved removal choices from reviewed groups across the entire scan, deduplicates files, and excludes untouched recommendations. The same token, expiry, fresh validation and explicit `/cleanup/execute` confirmation apply. Limit: 1,000 files per plan.

`GET /groups` and `GET /scans/{id}/matches` return groups in stable first-publication order (`first_seen_at`, then ID). A pending single-file group receives its timestamp only when it becomes a visible match; later membership updates do not move it ahead of other results.

`POST /scans/{id}/checkpoint` pauses a scan and waits for its worker to stop before returning the saved checkpoint. Resume with `POST /scans/{id}/resume`. The legacy `/pause` action requests a pause without waiting.

`POST /app/shutdown` requires `{"confirmed":true}`. It prevents new work, waits for active cleanup, pauses active scans, joins scan workers, commits checkpoint state, then requests graceful server shutdown after sending the response. Available for the server launched through `./run.sh`; custom hosts must provide a shutdown callback. The frontend stops polling and displays a safe-to-close page.

Group filtering and batch cleanup: `GET /groups` and `GET /scans/{id}/matches` accept optional `classification=EXACT_DUPLICATE|SIMILAR_CONTENT` and `sort=discovered|exact_first|largest|most_files` (default `discovered`). Filtering and sorting happen before pagination; `total` reflects the filter, while live exact/similar counts still describe the whole scan. Discovery order appends newly published groups; other sorts can move groups as scanning adds members.

`POST /groups/{id}/review` with `{ "changes": {} }` accepts the current selections and marks the group reviewed without toggling a file. `POST /cleanup/plan-selected` accepts optional `classification` with the same values. It includes selected exact copies (including automatic defaults) and reviewed similar groups matching that classification across all pages. Omitting it includes both classifications. The frontend batch scope follows its group filter. Duplicate Review checkboxes mean selected for deletion and save changes immediately; no separate mark-reviewed button is required. Every batch still opens a dry-run preview and requires confirmation before moving files.

Exact-duplicate review requires at least one ready keeper for ordinary checkbox changes. Explicit `keep_ids: []` (the “Select all for deletion” action) authorizes keeping none for that group. Keeping any member again clears this exception. Cleanup validates retained copies across overlapping exact groups at preview and execution; removing an entire exact group requires its explicit keep-none selection and all members in the cleanup. Protected-file restrictions and final confirmation still apply.

Cleanup plan items include optional `review_files` once per group: a saved snapshot of every ready member (`id`, `name`, `path`, `size`, `media_type`). The read-only confirmation partitions that snapshot using all planned deletion IDs, with kept files on the left in green and deletions on the right in red. It shows all retained members, not just the single verification keeper. Older plans without snapshots fall back to their recorded source/keeper paths.

Group-specific review and cleanup validation errors include the persistent group ID and up to three member filenames. The ID is also displayed on review cards and cleanup preview groups, so errors can be matched to groups even when filtering or sorting changes their page positions.

The batch action is labeled “Review exact duplicate groups”, “Review similar media groups”, or “Review selected groups” according to the active filter. It opens confirmation rather than executing deletion. The review scope is also displayed in that window and comes from the actual plan items.

Explicit “Select all for deletion” authorization survives live group rebuilds and scan resume for the previously selected members. It remains valid for per-group and filtered batch cleanup, including the final pre-move checks. Newly discovered files are not automatically authorized for removal.

After confirmation, the desktop review window shows validation followed by deletion progress, polling `GET /cleanup/{id}/progress` every 400 ms while execution is pending. `processed` includes moved and failed files; validation is indeterminate until whole-plan checks finish. Progress reads do not take the cleanup execution lock. The final response displays completed/partial results and individual errors.

The scan progress header also displays `selected_files / total_files` from the current group filter. `GET /scans/{id}/selection-summary?classification=EXACT_DUPLICATE|SIMILAR_CONTENT` returns these counts; omit classification for all matching groups. Both counts deduplicate overlapping group memberships and exclude unavailable/deleted files and resolved/pending groups. Selection eligibility matches batch cleanup (exact defaults plus manually reviewed similar selections). The current classification filter is shared between Scanner, Duplicate Review, and preview headers, and counts refresh after saved choices and cleanup.

The progress header provides “Stop scan” beside “Pause & save checkpoint”. Pause allows resume; stop ends the scan (`cancelled`) after waiting for the worker to stop, retaining completed results and checkpoints. Start a new scan to scan again. Dashboard's “Clear dashboard view” is a local, reversible dismissal of displayed scan/cleanup entries and latest metrics; it does not remove server history, media, checkpoint caches, or recovery records. “Restore cleared entries” makes them visible again. New scan IDs appear normally.

After a successful Stop scan, the desktop clears the selected scan and returns to a fresh Scanner setup. The “Reset scanner” action does the same; when the selected scan is active or paused, it safely stops it first. Reset closes previews, clears the group filter and pagination, and preserves folder/mode preferences and historical scan/cleanup records. Starting again creates a new scan ID rather than resuming the stopped scan.

`GET /scans/{id}` includes `checkpoint_storage.database` (the absolute SQLite checkpoint database path) and `checkpoint_storage.folder_caches` (absolute `.media-cleaner-cache` paths under the scan roots). Scanner displays these under File activity → Checkpoint & recovery. Cache folders contain per-file JSON entries in hash-prefix subfolders; folder cache failures remain visible in scan warnings.
