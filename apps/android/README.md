# Media Cleaner for Android

A standalone, offline native Android app for Android 11+ (API 30+). It does not require the desktop server, Python on the phone, or an account. The app requests photo/video access through Android permissions and scans only the media Android grants access to, including selected-only access on Android 14+.

## Use

1. Install the debug APK from `app/build/outputs/apk/debug/app-debug.apk` on your Android phone (transfer the file and open it; Android may ask you to allow installation from that file manager).
2. Allow photo/video access. Choose all accessible media or an album, then **Scan**.
3. Watch live groups, file progress, cache reuse and skipped-file warnings. **Pause** and **Resume** preserve completed-file checkpoints. Closing the activity does not stop the foreground scan; a process restart leaves the job available for explicit Resume.
4. Inspect thumbnails and full previews. **Compare similar videos** provides muted playback, shared play/pause/reset and deletion checkboxes. It pages through up to four simultaneous players to respect phone decoder limits. Unmute individual players to check audio.
5. Select unwanted files in a group and choose **Delete selected**. Keep at least one file; RAW and possible photo/video companion files are protected. Similar groups initially keep every item. Unambiguous copy filenames receive an advisory original recommendation after completion; explicit choices take priority.
6. Review the selected filenames and retained file, check the confirmation box, then continue. The app freshly hashes selected files and their retained copy before opening Android's own Trash confirmation. Scanning pauses for this workflow and resumes afterward when it was running. Cancelling does not move files. There is no permanent-delete operation.
7. **Cleanup and recovery** records the outcome and can request Android confirmation to restore items from Trash. Availability and retention are controlled by the device; gallery Trash is another recovery route. Rescan restored files to include them again.

## Build

Open this directory in Android Studio, using **JDK 21**, SDK platform **35**, and build tools **35.0.0**. The pinned build uses AGP 8.9.2 and the checked-in Gradle 8.11.1 wrapper with a distribution checksum.

From the repository root on macOS/Linux, with `JAVA_HOME` and `ANDROID_HOME` set (or the local tools below installed):

```sh
./build-android.sh
```

Or from this directory, including Windows:

```sh
./gradlew :matching:test :app:assembleDebug :app:lintDebug
# Windows: .\gradlew.bat :matching:test :app:assembleDebug :app:lintDebug
```

Output: `app/build/outputs/apk/debug/app-debug.apk`. This is an installable **debug/testing build**, not a signed Play Store release. Release signing/distribution and current store submission requirements are separate work. The local debug signing key is ignored; keep it if you want to update an installed debug app without uninstalling.

For a fresh clone on **macOS Apple Silicon**, install **Python 3.12+** and **curl**, then run from the repository root:

```sh
./setup-android.sh
./build-android.sh
```

Setup downloads checksum-verified JDK 21 and Android SDK 35 into ignored `.tools/android`, reuses existing downloads and installed components, and prompts for Google's SDK licenses when needed. No desktop setup, Android Studio or shell profile changes are required. The checked-in Gradle wrapper downloads its pinned distribution on the first build. Internet access is required for initial tools and build dependencies. Other hosts should install JDK 21 and Android SDK 35 manually and set `JAVA_HOME` and `ANDROID_HOME`.

`./setup-andriod.sh` is an alias for the requested spelling. Use `./setup-android.sh --accept-licenses` only after agreeing to [Google's SDK license](https://developer.android.com/studio#terms-and-conditions). Add `--emulator` to also download the optional Android 35 ARM64 emulator/system image (several GB); it is not required to build an APK. `PYTHON=/path/to/python3.12` can select the bootstrap interpreter.

The root build runs matching tests, APK compilation and Android lint, then copies the APK and SHA-256 checksum to `.tools/dist/media-cleaner-android-debug.apk` and `.tools/dist/media-cleaner-android-debug.apk.sha256`. It accepts Gradle options, for example `./build-android.sh --offline` after dependencies have been downloaded. Both root scripts work when called from another directory. Downloaded tools, build caches and APKs are ignored by Git; a new clone downloads them again. No build tools are downloaded at app runtime.

## Boundaries and matching

- `app/`: native Android UI, MediaStore access, foreground scanner, private SQLite checkpoints, fresh-hash validation and system Trash/restore integration.
- `../../shared/matching/`: pure Java matching code and JVM tests, with no Android dependency.
- `scripts/`: local tool bootstrap, build, and emulator smoke testing.

SHA-256 covers supported accessible media regardless of visual decoder availability. Still photos use 64-bit DCT pHash and dHash, aspect/color checks and complete-link groups. Videos use nine time-spaced native-decoder samples, a duration tolerance, at least six common informative samples and at least 80% compatible common samples. Static/low-detail sequences are excluded from approximate matching. A BK-tree indexes candidate groups; every member must satisfy pairwise checks. Exact-only content is not duplicated as an approximate group.

Android descriptors have their own `android-phash-dhash-v1` version. Their pixels/resampling/native decoders can differ from desktop implementations; binary-identical fingerprints and cross-platform cache interchange are not claimed. Video audio, every-frame equivalence, arbitrary trims/crops, semantic matching and animated-image sequence matching are not implemented. Animated images currently retain exact matching only. Actual camera/codec support varies by phone.

## Storage and limits

Checkpoints, cached analysis, selections and cleanup history live in the app's private `databases/media-cleaner.sqlite3`. Android MediaStore URIs replace desktop filesystem paths. The desktop `.media-cleaner-cache` format is not used or imported. Uninstall/Clear storage removes this app data; gallery media and Android-managed Trash are separate. Backup/transfer of the app database is disabled and the APK requests no Internet permission.

A scan indexes accessible local photo/video collections; it is not an arbitrary-filesystem or cloud-library scanner. Permissions can limit or revoke visibility. The scanner validates MediaStore size/modification/generation identity before reusing completed work and before/after hashing. A changed media item is processed again. Cleanup is serialized by pausing the worker, requires a verified retained item and fresh content checks, and delegates the actual move to Android confirmation. The provider can change between app verification and its system dialog; device/provider behavior needs real-phone validation.

Large groups are limited in visible UI, and comparison uses four players per page. Cleanup previews accept at most 100 items at a time. English UI, Android API 35 emulator validation and a debug APK are provided; broad phone/OEM/codec coverage, app-store release certification and desktop feature parity are not claimed. Long scans are subject to Android foreground-service/battery restrictions; saved files can be resumed.

## Verification

`build.sh` runs pure Java matching tests, APK compilation and Android lint. Current delivery validation: 5 matching tests passed; Android lint has no errors (13 English-string localization warnings); the Android 15/API 35 ARM64 emulator completed the synthetic gallery, checkpoint reuse, last-keeper guard, cancelled preview, confirmed Trash and restore flow. The debug APK signature was verified. The synthetic-only emulator script refuses physical devices and any AVD name other than `media-cleaner-test`; it clears only this app's test data and uses generated gallery media. It verifies actual photo/video matching, checkpoint reuse, comparison selection, retained-file protection, app confirmation, Android Trash and restore. It requires the repository's desktop Python test environment only for generating synthetic images/videos.

```sh
# Start the isolated AVD (separate terminal; waits for boot):
./apps/android/scripts/emulator.sh
# Install the current APK into that AVD only:
.tools/android/sdk/platform-tools/adb -s emulator-5554 install -r apps/android/app/build/outputs/apk/debug/app-debug.apk
.venv-phase1/bin/python apps/android/scripts/emulator-smoke.py
```

Screenshots are written to ignored `.tools/android/smoke`. Do not point tests at personal media or a physical device. The existing desktop app and Windows files remain separate under `apps/desktop`.
