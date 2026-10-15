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
| GET /files/{id}/preview | Normalized image preview or range-capable original video |
| GET /groups?scan_id=... | Paginated unresolved exact/similar groups, ordered by savings |
| GET /groups/{id} | Paginated current members and saved keep choices |
| POST /groups/{id}/review | Set `keep_ids` or partial `changes:{file_id:boolean}`; at least one keeper |
| POST /cleanup/plan | Dry run for `file_ids`, `group_id` (required for approximate groups), destination `trash` or `quarantine` |
| POST /cleanup/execute | `plan_id`, matching plan `token`, `confirmed:true` |
| GET /cleanup/history | Paginated plans, outcomes and recovery records |
| POST /cleanup/{id}/restore | `confirmed:true`; quarantine recovery only |
| GET /settings | Current validated preferences |
| PUT /settings | Save protection/exclusions, workers, theme and destination |
| GET /diagnostics | Download rotating local diagnostic log |

List responses are `{items,total}` with `offset`/`limit`, except the observed-volume list. Limit caps vary from 100 to 200 by resource. A scan root must be an existing directory. Multiple roots share one scan and physical-file deduplication. Live groups are provisional; only completed scans permit review writes and cleanup. Approximate groups require a saved manual review and an explicit group-scoped plan. Protected choices cannot be unchecked. No arbitrary shell commands, arbitrary preview paths, arbitrary shell access or permanent-delete API is exposed.

The `similar` mode now compares still photos/RAW and video/animation sequences. Sequence evidence includes `media_kind:sequence`, sample counts, duration difference, algorithm version and limitations. It remains approximate and requires manual review; no audio equality is asserted.
