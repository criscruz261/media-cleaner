# Android app boundary

Android-specific source, resources, manifests, build configuration and tests belong here. This directory reserves a separate application boundary; no Android project, APK or device-scanning implementation has been created yet.

The desktop FastAPI server and desktop filesystem/Trash implementation remain under `apps/desktop`; do not import those as an Android runtime. An Android implementation must supply its own media-access, permission, decoding, background-scan and confirmed-cleanup adapters.

Cross-platform data definitions belong in `shared/contracts`. The existing TypeScript definitions describe the current desktop transport; an Android client may need generated or equivalent native models once its implementation technology is chosen. Reusable behavior and test vectors can be extracted to `shared` as real Android requirements emerge.

Keep machine-specific Android SDK paths, signing keys, build caches and generated APK/AAB files out of Git. Dependency manifests, lockfiles, Gradle wrapper files and source should be committed when an Android project is added.
