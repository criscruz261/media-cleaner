# Portable JVM matching core

Pure Java 17 library consumed by the Android app. It has no Android, filesystem, media permission, database or UI dependency. Desktop Python continues to use its own implementation; this extraction does not replace it.

`Matcher` implements SHA-256 group indexing, 64-bit photo signatures, BK-tree candidate search, complete-link appearance groups, sampled-sequence duration/detail checks, and advisory copy-name recommendations. Pixel decoding, SHA-256 calculation, persistence, keep selections and confirmation remain application adapters. Android's descriptor version is explicit; matching desktop fingerprints byte-for-byte is not asserted.

Run `./gradlew :matching:test` from `apps/android`, or use the Android build script. Tests cover exact/similar separation, original recommendations, weak-chain rejection, low-detail rejection and video sample/duration constraints.
