# Similar-photo delivery

The Scanner now defaults to **Similar photos + exact media copies**. It compares decoded still images with versioned 64-bit pHash and dHash descriptors from ImageHash, after thumbnail and EXIF-orientation normalization. Exact video/photo matching continues in this mode, and the existing exact-only modes remain available. Heavy crops, arbitrary rotation, semantic scene similarity, RAW rendering, animation sequences, and re-encoded video matching are not claimed.

Sensitivity presets are algorithm distances, not confidence percentages:

| Preset | Maximum pHash distance | Maximum dHash distance |
| --- | --- | --- |
| Strict | 4 / 64 bits | 6 / 64 bits |
| Balanced (default) | 8 / 64 bits | 10 / 64 bits |
| Broad | 12 / 64 bits | 14 / 64 bits |

Every pair in a group must satisfy both hash limits, a normalized aspect-ratio difference check (absolute log ratio <= 0.1), and a per-channel average-color difference <= 60/255. Low-detail stills (grayscale standard deviation below 8) and animated images are omitted from perceptual matching with per-file warnings, while exact hashing still works. These are conservative heuristics tested on synthetic resized, recompressed, brightness-adjusted and unrelated fixtures, not a calibrated real-world photo benchmark. False positives and false negatives remain possible; inspect the previews.

Candidate search uses a BK-tree over unique pHash values; the second hash and appearance constraints verify candidates. Complete-link grouping checks all unique descriptors within each candidate group, preventing A~B~C similarity chains from incorrectly including A and C when they do not qualify. BK-trees avoid unconditional all-pairs library comparison, but worst-case search and very dense candidate groups can still be expensive. No 100k-image performance guarantee is claimed.

The `fingerprints` table stores descriptor algorithm, version, identity cache key and JSON value. Alembic revision `0002` adds the indexed cache key without rewriting scan history. Unchanged descriptors are reused across scans; changed file identities invalidate them. SHA-256 is also calculated for every still image in similar mode so subsequent manual cleanup can independently revalidate each file's content. Pairwise representative evidence is persisted in `similarity_matches`.

Approximate groups are classified **SIMILAR_CONTENT**, never promoted to exact equality or safe duplicates. The UI displays “Similar photos · review required,” pairwise maximum pHash/dHash distances and thresholds. Every similar-group member starts kept, with no automatic removal recommendation. Review choices are scoped to their group. Exact groups can overlap a similar group; the UI explains this. The dashboard counts exact and similar groups separately and sums exact-copy savings only, avoiding overlap double-counting.

Manual cleanup is supported only after the user unchecks files, saves the review, requests a group-scoped dry-run plan, reviews the similar-photo warning, and confirms. Selected and kept files are freshly verified against their own SHA-256 values, rather than incorrectly requiring visually similar files to have equal bytes. Retained-copy changes after a preview require a new plan. RAW/companion/protected-folder rules, Trash/quarantine, explicit confirmation, recovery records and no-overwrite restore remain in force. No automatic approximate-match deletion or permanent-delete endpoint exists.

Changed areas: `backend/app/similarity/images.py`, worker integration, request schemas, cleanup validation, dashboard aggregation, `fingerprints` model/migration, backend dependency manifests/lockfile, React Scanner/Review/Cleanup/Dashboard/types, regression tests, browser fixture tooling and documentation. Existing source remains modular; no media is sent to a server outside the local app.

Validation includes cross-format/resizing/brightness comparisons, unrelated fixtures, EXIF orientation, corrupt/flat/animated files, indexed-versus-exhaustive Hamming search, real complete-link grouping, fingerprint reuse/invalidation, manual approximate quarantine with a different-content keeper, exact-video compatibility, dashboard separation and invalid-sensitivity rejection. Validation passed: Ruff, 34 backend tests, 3 frontend tests, TypeScript/Vite production build, and the real Chrome scan → similar-photo manual review → confirmed quarantine → restore workflow. One existing Starlette/httpx test-client deprecation warning remains.

Run `./run.sh`, open the printed launch link, refresh the browser, choose Similar photos in Scanner, and start a **new scan**. Historical exact-only scans are not silently reclassified. Fresh clones should run the normal setup script to install the updated ImageHash/NumPy/SciPy dependencies before starting.

Next work remains broader corpus calibration and additional cross-format fixtures, followed by Phase 3 multi-frame video similarity. Crop-aware embeddings and partial-video alignment remain Phase 4, desktop installers Phase 5.

Implementation reference: [ImageHash pHash/dHash and Hamming distance](https://github.com/JohannesBuchner/imagehash).
