# Algorithms and evidence

Phase 1 discovers registered image/video extensions case-insensitively. Filename extension selects the handler, not a claimed codec. FFprobe, when installed, identifies streams and actual container/codec information. Unsupported/corrupted metadata does not prevent binary hashing.

Exact comparison groups by file size in SQLite, then computes the complete SHA-256 for size candidates in 1 MiB chunks. Only matching complete digest and size are `EXACT_DUPLICATE`. Unique-size files still receive metadata but do not require a digest. Identity is checked before/after hashing and cleanup rehashes both selected and retained copies. No partial hash proves equality. Results show algorithm, digest, paths, sizes and potential savings.

Retention favors a protected original/asset. Otherwise, if exactly one member lacks “copy”, “duplicate” or a trailing numbered-parentheses marker, it is suggested. Multiple plausible originals means manual selection, with every file initially kept. File size, capture time and filesystem timestamps do not prove originality or image quality. Recommendations only concern equal bytes in Phase 1.

Pillow normalizes EXIF orientation and creates bounded-dimension image previews. HEIF uses pillow-heif. Animated-image metadata includes frame count and animation flag, but the current preview is a still. RAW exact matching works; RAW rendering and verified RAW/export relationships remain later work. FFprobe records duration, dimensions, frame-rate rational, codec, audio/video stream counts, bitrate, container and raw stream details. ExifTool data is retained when installed. Timestamp strings remain as supplied when timezone is ambiguous.

Phase 2 will add versioned pHash/dHash, candidate indexing and tested thresholds, keeping same-content and approximate relations separate. Phase 3 adds multiple-temporal-position frame comparison via FFmpeg/FFprobe. Phase 4 adds crop-aware/embedding comparison and temporal partial-overlap alignment. These are not enabled options or implemented classifiers yet. No universal confidence percentage or unsupported accuracy/performance guarantee is displayed.
