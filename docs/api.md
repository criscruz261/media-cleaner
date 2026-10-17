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
| POST /scans/{id}/cancel | Request checkpoint cancellation |
| POST /scans/{id}/resume | Resume paused/interrupted/failed job when worker has stopped |
| GET /scans/{id}/warnings | Paginated skipped-analysis and metadata warnings |
| GET /scans/{id}/events | SSE progress snapshots and heartbeat; closes at a terminal state |
| GET /volumes | Previously observed volumes; not an exhaustive OS volume picker |
| GET /files?scan_id=... | Paginated inventory; optional status filter |
| GET /files/{id} | Identity, status, metadata and warnings |
| GET /files/{id}/thumbnail | Small JPEG still/video poster; identity checked, bounded in-memory cache |
| GET /files/{id}/preview | Normalized image preview or range-capable original video |
| GET /groups?scan_id=... | Paginated unresolved exact/similar groups, ordered by savings |
| GET /groups/{id} | Paginated current members and saved keep choices |
| POST /groups/{id}/review | Set `keep_ids` or partial `changes:{file_id:boolean}`; empty `keep_ids:[]` selects the entire group for deletion; protected assets must stay kept |
| POST /cleanup/plan | Dry run for `file_ids`, `group_id` (required for approximate groups), destination `trash` or `quarantine` |
| POST /cleanup/execute | `plan_id`, matching plan `token`, `confirmed:true` |
| GET /cleanup/history | Paginated plans, outcomes and recovery records |
| POST /cleanup/{id}/restore | `confirmed:true`; quarantine recovery only |
| GET /settings | Current validated preferences |
| PUT /settings | Save protection/exclusions, workers, theme and destination |
| GET /diagnostics | Download rotating local diagnostic log |

List responses are `{items,total}` with `offset`/`limit`, except the observed-volume list. Limit caps vary from 100 to 200 by resource. A scan root must be an existing directory. Multiple roots share one scan and physical-file deduplication. Live groups can gain members; review writes and confirmed cleanup are available during and after scanning. Only already processed, verified group members are eligible. Cleanup from a different scan is blocked while another scan is active. Approximate groups require a saved manual review and an explicit group-scoped plan. Protected choices cannot be unchecked. No arbitrary shell commands, arbitrary preview paths, arbitrary shell access or permanent-delete API is exposed.

The `similar` mode now compares still photos/RAW and video/animation sequences. Sequence evidence includes `media_kind:sequence`, sample counts, duration difference, algorithm version and limitations. It remains approximate and requires manual review; no audio equality is asserted.

`POST /api/v1/cleanup/plan-selected` takes `scan_id` and `destination` (`trash` or `quarantine`). It previews saved removal choices from reviewed groups across the entire scan, deduplicates files, and excludes untouched recommendations. The same token, expiry, fresh validation and explicit `/cleanup/execute` confirmation apply. Limit: 1,000 files per plan.
