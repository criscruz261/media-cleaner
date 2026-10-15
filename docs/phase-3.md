# Similarity across photos, videos, animations and RAW

The default scan is now **Similar photos, videos & animations**. Existing exact-only modes remain available. Supported media extensions are registered in `core/filesystem.py`; actual video streams are probed, not inferred from the extension. All supported camera RAW extensions use LibRaw through rawpy for visual decoding. There is no claim that arbitrary proprietary codecs, standalone audio, documents, or every file extension can be visually compared.

## Still images and RAW

Pillow/pillow-heif handles supported JPEG, PNG/APNG, HEIC/HEIF, WebP, TIFF, BMP, GIF and AVIF images. rawpy uses an embedded RAW thumbnail when available, otherwise half-size demosaicing with a size limit. Camera orientation is normalized. RAW extensions include DNG, CR2/CR3, NEF, ARW, ORF, RW2, RAF, PEF, SRW, 3FR and RWL; LibRaw support varies by camera. Unsupported/corrupt files are reported, not fabricated as successful matches. RAW originals remain protected from cleanup.

Normalized still descriptors use `imagehash-phash-dhash`, version 2. The version was bumped because the shared still/RAW normalization pipeline changed; old fingerprints are retained but not reused by the new algorithm. Photo matching retains the strict/balanced/broad pHash+dHash thresholds, color/aspect checks and complete-link grouping from Phase 2. The RAW fixture test generates a synthetic Bayer DNG and verifies comparison to its rendered PNG and a working JPEG preview. It does not certify every camera model.

## Videos and animation sequences

FFprobe discovers the real first video stream and its duration, dimensions, frame rate and codec/container. FFmpeg samples nine positions `(slot+0.5)/9` across the video. Seeking is adjusted by the nominal frame interval to choose the displayed frame rather than the next frame, including the last display interval. Frames are oriented by FFmpeg and scaled with display aspect ratio to at most 256 pixels per dimension. Each informative frame receives pHash/dHash plus aspect/color descriptors. Black/low-detail frames are omitted.

Animated GIF/WebP/APNG and other Pillow-supported timed animations use the same nine normalized timeline positions. Frame durations are loaded explicitly; missing/nonpositive timing is reported rather than invented. Animations over 2000 frames are skipped for perceptual analysis. Animated previews stream the original browser-compatible asset, instead of silently converting it to a still. An animation can match a video export when duration and sampled visual sequence qualify.

Descriptors use `temporal-phash-dhash`, version 2. There must be at least six informative samples and two distinct visual descriptors. Candidate indexing combines logarithmic duration buckets with a pHash BK-tree at each temporal slot. At least six indexed slots must qualify before full sequence comparison. Complete-link grouping requires every distinct member sequence to match every other member; no weak transitive chains are accepted.

| Sensitivity | Duration tolerance | Required comparable-frame match ratio | Frame pHash / dHash limits |
| --- | --- | --- | --- |
| Strict | max(0.25 seconds, 1% of shorter duration) | 100%, minimum 6 samples | 4 / 6 bits |
| Balanced | max(0.25 seconds, 3%) | 85%, minimum 6 | 8 / 10 bits |
| Broad | max(0.25 seconds, 6%) | 75%, minimum 6 | 12 / 14 bits |

The percentages above are matching rules, **not confidence or validated accuracy percentages**. Every qualifying frame also passes aspect/color checks. Identical repeated title cards alone cannot establish a match; changing shared frames are required. Duration is a candidate constraint, never proof of equality. Static or low-detail video can be skipped conservatively even when it looks related; exact detection remains available.

This detects some re-encoded/resized/cross-container clips and frame-rate changes. It does not implement arbitrary trims, partial overlap, playback-speed alignment, crop-aware matching, semantic embeddings or audio fingerprints. Nine samples do not inspect every frame. Two clips can have different audio, subtitles or unsampled moments despite qualifying visually. Results are always `SIMILAR_CONTENT`, never promoted to exact equality or safe-to-delete duplicates.

## Setup, runtime and warnings

Setup scripts install the locked `static-ffmpeg` helper and explicitly call `scripts/install-media-tools.py`. Existing system FFmpeg/FFprobe are used when both are available; otherwise the helper downloads platform binaries into the virtual environment. The helper's upstream binary provider is [zackees/ffmpeg_bins](https://github.com/zackees/ffmpeg_bins); the binaries tested in this workspace report FFmpeg/FFprobe 7.0, regardless of the helper archive directory's version label. Their licensing and provenance must be reviewed again for distributed installers. Downloaded tools remain ignored by Git. Existing environments can run:

```sh
.venv-phase1/bin/python scripts/install-media-tools.py
```

Runtime tool discovery checks `MEDIA_CLEANER_FFMPEG`/`MEDIA_CLEANER_FFPROBE`, system PATH, then already-downloaded virtual-environment binaries. Runtime never fetches tools or models. Decoder commands restrict inputs to local file/pipe protocols. Decoder subprocesses have time limits, cancellation checkpoints and guaranteed process cleanup. Metadata results and versioned descriptors are cached by identity. Similar mode SHA-256 hashes each media file for later cleanup revalidation, so the initial scan of large videos can require substantial disk reads.

The Scanner exposes a paginated list of per-file warnings from `/api/v1/scans/{id}/warnings`. Missing tools, corrupt containers, unavailable codecs, insufficient informative frames, missing animation timing, and RAW failures are visible there even when no group was created. Exact hashing continues for those files. ExifTool remains optional for richer metadata. Windows/Linux setup code is supplied, but this delivery's runtime tests are on macOS Apple Silicon.

## Review, cleanup and validation

Sequence groups show sample-match counts, maximum duration difference, frame-hash thresholds and an audio/unsampled-content warning. Every approximate member starts kept. The user must compare previews/playback, manually uncheck files, review a group-scoped cleanup plan and explicitly confirm Trash/quarantine. Each selected file and keeper is rehashed against its own snapshot. RAW, companion and protected-folder rules, no permanent deletion, audit records, and no-overwrite quarantine restore remain enforced.

Tests use generated media only: real MOV/MP4 with H.264 versus MPEG-4, changed resolution/frame rate/audio; unrelated clips; MKV remux; GIF/WebP and GIF/MP4; synthetic DNG/rendered PNG; invalid RAW/INSV; missing tools; sequence cache reuse; decoder cancellation; duration/order/shared-intro/static-frame rejection; duration-index candidates; and manual video quarantine/restore. Broader codec coverage, real-library threshold calibration and large-library performance remain unvalidated.

New source modules are `core/media_tools.py`, `metadata/decoding.py`, `similarity/temporal.py`, and `similarity/sequences.py`, with worker/API/metadata/frontend/setup integrations and regression tests. No new database schema is required beyond the prior versioned-fingerprint cache migration. Future work is Phase 4 partial/advanced matching and audio corroboration, followed by desktop packaging.

Implementation references: [FFmpeg command documentation](https://ffmpeg.org/ffmpeg.html), [ImageHash](https://github.com/JohannesBuchner/imagehash), [rawpy](https://github.com/letmaik/rawpy), [static-ffmpeg setup helper](https://pypi.org/project/static-ffmpeg/).

Delivery validation: **44 backend tests passed, 3 frontend tests passed, Ruff and TypeScript/Vite build passed**. The real Chrome fixture passed scan → video similarity evidence → actual playback → manual selection → confirmed quarantine → restore, with desktop/mobile screenshots. One existing Starlette/httpx test-client deprecation warning remains. No real user media was changed.
