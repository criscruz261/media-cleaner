# Database

SQLite runs with `journal_mode=WAL`, foreign keys ON, and a 30-second busy timeout. Startup upgrades through Alembic revision `0003`; revision `0001` creates the initial schema and `0002` adds the image-fingerprint cache-key index; `0003` adds persistent scan byte totals and group update timestamps, backfilling existing history. The migration explicitly declares columns, indexes and constraints; it does not import mutable application metadata. Later schema changes require a new revision. Back up a stopped database and its WAL safely before upgrades; do not move an active WAL database onto network storage.

| Table | Role |
| --- | --- |
| volumes | Observed mount/device identity and last-seen path |
| scan_roots | Roots attached to a historical scan; availability recorded separately |
| scan_jobs | Options, lifecycle, stages, counters and errors |
| files | Per-scan identity snapshots, media types, statuses and hashes |
| media_metadata | Normalized image/video data, useful raw data and warnings |
| file_hashes | SHA-256 and metadata cache keyed by canonical path + full identity |
| fingerprints | Versioned still/RAW and video/animation descriptors with indexed identity cache keys |
| similarity_matches | Representative image-pair evidence and approximate classifications |
| duplicate_groups | Exact classification, evidence, recommendation and review state |
| group_members | Saved per-file keep choices |
| cleanup_operations | Expiring dry-run plans, per-item intent, outcomes and recovery paths |
| settings | Validated application preferences |

Foreign keys tie files/roots/groups to history. `(scan_id,path)` and `(scan_id,device,inode)` are unique. Exact grouping indexes scan/size/SHA-256. Snapshot files are never removed merely because a root is unavailable. No cross-platform stable hardware UUID is claimed; remounts may require a new scan. Byte counts represent logical file sizes rather than filesystem allocation or guaranteed reclaimed space.

Cached equality is reused only for unchanged canonical path, device, inode, size, mtime and ctime. A formerly unique file may have cached metadata without a digest; it receives a full digest if a later scan finds equal-size candidates. Algorithm identifier is `sha256-v1`. The current similar-photo mode generates and caches image descriptors; see [Phase 2](phase-2.md).

Current descriptor versions are imagehash-phash-dhash v2 and temporal-phash-dhash v2. Previous versions remain historical and are not reused by updated algorithms. No new schema migration is needed for temporal descriptors.
