# Media Cleaner for Android

A standalone, offline native Android app for Android 11+ (API 30+). It does not require the desktop server, Python on the phone, or an account. The app requests photo/video access through Android permissions and scans only the media Android grants access to, including selected-only access on Android 14+.

## Interface

Dark mode is enabled by default. Use **Settings → Appearance → Dark mode** to
switch between dark and light themes; the choice persists after restarting.
Page surfaces, controls, dialogs, system bars, and keep/delete colors follow the
selected theme. Switching themes preserves saved scan and review data.

The phone app follows the desktop's five sections using bottom navigation:
**Dashboard**, **Scanner**, **Review**, **Cleanup**, and **Settings**. The green
and cream palette, bordered cards, buttons, preview controls, and cleanup dialogs
follow the desktop style with touch-sized controls. Labels use sentence case.
Review displays numbered groups as full-width rows. Each row shows its position
in the active filter, including unloaded pages. Group actions sit together below
the files; thumbnails and compact filenames come first, with file selection
controls beneath them.
Files within each group appear side by side as width permits (up to four
columns), with Comfortable, Compact, and Very compact density options saved on
the device. Narrow screens fall back to a single file column.
Its banner shows filtered group counts and unique selected/total files across all
pages. Scrolling on any page collapses its header to a 48 dp summary. Review keeps
counts and the active filter; Dashboard keeps file/group counts; Scanner keeps
status and progress; Cleanup keeps request/pending-confirmation information;
Settings keeps storage/privacy context. Running scan progress remains available
in compact summaries. Return to the top, swipe downward, or tap the summary to expand it. Header transitions are
animated, and the compact summary shows an expand arrow. Upward/downward
gestures work even when the page fits entirely onscreen. Exact-duplicate and similar-media filters also scope batch cleanup.
File cards are green for kept files and red for files selected for deletion;
checkboxes and text provide the same state without relying on color alone.
The checkpoint-and-shutdown action is red. Scan progress stays visible
across sections and inside media previews. Switching sections preserves review
selections, filters, expanded groups, and each section's scroll position.

Choose a scan mode from the dropdown, then press the main button to start.
Selecting a mode only updates the label.

Scanner uses three steps: **Scan setup → Scan → Review matches**.
The **Scan** button always recomputes hashes and visual analysis for selected
media. Its dropdown offers **Continue Scan** when a saved scan exists, reusing
completed analysis and continuing the saved media selection. New results replace
analysis progressively; media and cleanup history are preserved.

Media selection appears before the access button. Scan has a dropdown;
checkpoint controls remain available, with shutdown under expandable Session
options. Contextual guidance explains when matches can be reviewed.

Review uses **Choose matches → Compare and select → Clean up selections**.
Filter and sort controls share a row, compactness remains adjustable, and batch
cleanup follows the results with an explanation of the app preview and Android
confirmation. Per-group selection and deletion actions remain available. Select all for deletion
changes to Unselect all for deletion when every file is selected; unselecting
keeps every file. Explicit file choices are included in batch cleanup without
a separate mark-reviewed action. Groups with no selected files are skipped
when preparing batch cleanup, so keeping an entire group does not block
selections in other groups.

Dashboard shows the latest scan's file count, exact and similar group counts,
and shortcuts. Scanner handles album selection and checkpoints; Review contains
live matches, filters, comparisons and batch cleanup. Cleanup contains operation
history and restore actions. Settings provides Android media permissions,
storage/privacy information, and checkpoint-and-shutdown. Android continues to
control media permissions and the final Trash/restore confirmation. This shares
the desktop's organization while showing only features available on Android.

## Use

1. Install the debug APK from `app/build/outputs/apk/debug/app-debug.apk` on your Android phone (transfer the file and open it; Android may ask you to allow installation from that file manager).
2. Allow photo/video access. Choose all accessible media or an album, then **Scan**.
3. Watch live groups, file progress, cache reuse and skipped-file warnings. **Pause** and **Continue Scan** preserve completed-file checkpoints. Closing the activity does not stop the foreground scan; a process restart leaves the job available for explicit Continue Scan.
4. Inspect thumbnails and full previews. **Compare similar videos** provides muted playback, shared play/pause/reset and deletion checkboxes. It pages through up to four simultaneous players to respect phone decoder limits. Unmute individual players to check audio.
5. Select unwanted files in a group and choose **Delete selected**. Use **Select all for deletion (keep none)** to remove the whole group; RAW and possible photo/video companion files are protected. Similar groups initially keep every item. Unambiguous copy filenames receive an advisory original recommendation after completion; explicit choices take priority.
For multiple groups, make selections in each, then use **Delete selected across groups** above the groups. This includes groups with explicit choices outside the visible page and excludes untouched suggestions. One combined preview and Android confirmation covers up to 100 distinct files, including keep-none groups.

6. Review the selected filenames and retained file (or the **Keep none** notice), check the confirmation box, then continue. The app freshly hashes selected files and their retained copy before opening Android's own Trash confirmation. Scanning pauses for this workflow and resumes afterward when it was running. Cancelling does not move files. There is no permanent-delete operation.
7. **Cleanup and recovery** records the outcome and can request Android confirmation to restore items from Trash. Availability and retention are controlled by the device; gallery Trash is another recovery route. Rescan restored files to include them again.

## Numbered scripts

From the repository root:

```sh
./scripts/android/1-setup.sh
./scripts/android/2-build.sh
# In a separate terminal, start the visible emulator:
./scripts/android/5-start-emulator.sh
# After the Android home screen appears:
./scripts/android/3-run.sh emulator-5554
./scripts/android/4-create-deploy-package.sh
```

Setup installs local tools on macOS Apple Silicon and discovers compatible
Python automatically. It prompts for SDK licenses; optional `--emulator`
installs emulator components. On other hosts configure JDK 21 and SDK 35 manually.
Build runs matching tests, compiles the native app, and runs lint; Android has
no separate frontend/backend builds. Run requires an explicit serial from
`adb devices` and an already running emulator or connected, authorized phone.
It installs the APK with `adb install -r` and launches the app. Start the optional
test emulator separately using `./apps/android/scripts/emulator.sh`.

Packaging rebuilds, verifies the APK signature, and publishes the debug APK,
SHA-256 checksum, and installation README to `deployment-package/android/`.
Transfer the APK to an Android 11+ device to install it. Build and packaging accept
Gradle options such as `--offline`. Each script supports `--help`. Release
signing and Play Store packaging are separate work.

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

SHA-256 covers supported accessible media regardless of visual decoder availability. Still photos use 64-bit DCT pHash and dHash, aspect/color checks and complete-link groups. Videos use 6–24 time-spaced native-decoder samples (default nine), a duration tolerance, and at least six common informative samples. Strict requires all common samples to match, Balanced requires 85%, and Loose requires 75%, always with at least six matching samples. Static/low-detail sequences are excluded from approximate matching. A BK-tree indexes candidate groups; every member must satisfy pairwise checks. Exact-only content is not duplicated as an approximate group.

Android descriptors have their own `android-phash-dhash-v1` version. Their pixels/resampling/native decoders can differ from desktop implementations; binary-identical fingerprints and cross-platform cache interchange are not claimed. Video audio, every-frame equivalence, arbitrary trims/crops, semantic matching and animated-image sequence matching are not implemented. Animated images currently retain exact matching only. Actual camera/codec support varies by phone.

## Storage and limits

Checkpoints, cached analysis, selections and cleanup history live in the app's private `databases/media-cleaner.sqlite3`. Android MediaStore URIs replace desktop filesystem paths. The desktop `.media-cleaner-cache` format is not used or imported. Uninstall/Clear storage removes this app data; gallery media and Android-managed Trash are separate. Backup/transfer of the app database is disabled and the APK requests no Internet permission.

A scan indexes accessible local photo/video collections; it is not an arbitrary-filesystem or cloud-library scanner. Permissions can limit or revoke visibility. The scanner validates MediaStore size/modification/generation identity before reusing completed work and before/after hashing. A changed media item is processed again. Cleanup is serialized by pausing the worker, requires a verified retained item and fresh content checks, and delegates the actual move to Android confirmation. The provider can change between app verification and its system dialog; device/provider behavior needs real-phone validation.

Large groups are limited in visible UI, and comparison uses four players per page. Cleanup previews accept at most 100 items at a time. English UI, Android API 35 emulator validation and a debug APK are provided; broad phone/OEM/codec coverage, app-store release certification and desktop feature parity are not claimed. Long scans are subject to Android foreground-service/battery restrictions; saved files can be resumed.

## Verification

`build.sh` runs pure Java matching tests, APK compilation and Android lint. Current delivery validation: 5 matching tests passed; Android lint has no errors (localization and backup-rule warnings remain); the Android 15/API 35 ARM64 emulator completed the synthetic gallery, checkpoint reuse, keep-none preview, cancelled preview, confirmed Trash and restore flow. The debug APK signature was verified. The desktop-style UI was checked across all five sections, media preview and video comparison, batch cleanup confirmation, Android Trash/restore, and checkpoint close/reopen/resume. The synthetic-only emulator script refuses physical devices and any AVD name other than `media-cleaner-test`; it clears only this app's test data and uses generated gallery media. It verifies actual photo/video matching, checkpoint reuse, comparison selection, keep-none selection, changed-file protection, app confirmation, Android Trash and restore. It requires the repository's desktop Python test environment only for generating synthetic images/videos.

```sh
# Start the isolated AVD (separate terminal; waits for boot):
./apps/android/scripts/emulator.sh
# Install the current APK into that AVD only:
.tools/android/sdk/platform-tools/adb -s emulator-5554 install -r apps/android/app/build/outputs/apk/debug/app-debug.apk
.venv-phase1/bin/python apps/android/scripts/emulator-smoke.py
```

Screenshots are written to ignored `.tools/android/smoke`. Do not point tests at personal media or a physical device. The existing desktop app and Windows files remain separate under `apps/desktop`.

Tap a group thumbnail to open a screen-fitting preview. **Previous/Next** navigates the full group, **Select for deletion** saves the same choice used by group and batch cleanup, and **Fit to screen** resets zoom. Photos support pinch zoom and drag panning as well as zoom buttons. Videos play in the preview with playback controls. Navigation resets zoom and stops the previous video.

New matching groups append at the end in first-seen order. Updates replace only the changed group card, preserving unaffected cards and expanded groups. Scan progress remains pinned above the scrolling results and appears inside photo/video review dialogs, with a reminder that groups may change during scanning.

**Save checkpoint** waits for the scanner to pause and finish saving completed work. **Continue Scan** rechecks access and continues using unchanged completed files. **Save checkpoint and close** asks for confirmation, waits for the checkpoint, stops the scan service, and closes the app task. Resolve any pending Trash/restore confirmation before using this action.

### Matching controls

Scanner offers a **Strict → Balanced → Loose → Very loose → Extra loose → Maximum** sensitivity slider. Balanced is
the default; Loose returns more candidates that need review. Exact SHA-256
duplicate detection is unchanged. The landscape examples illustrate small and
larger edits; they are not a promise that a specific pair will match.

**Video samples** selects 6–24 evenly spaced frames per video (default 9). More
frames cover more of the timeline and take longer; audio and unsampled moments
can still differ. Desktop applies this count to animations too. Cached frame
analysis is reused only when its sample count matches. Continue Scan uses the
saved settings for unfinished scans; Scan starts fresh with the chosen settings.
Android places these controls under **1. Scan setup → Matching options**.

The sensitivity section is centered. Very loose, Extra loose, and Maximum widen
perceptual hash and duration tolerances progressively. Maximum can include
unrelated candidates; inspect groups before deleting. The two-photo preview
uses progressively stronger display color edits for the added levels.

### Subject and scene variation

Similarity scans now use a bundled local image model alongside pHash/dHash.
Maximum can find broader subject/scene resemblance across movement, changed
poses, camera angles and backgrounds. Region features help when objects are
missing or obscured. Lower sensitivity levels require closer agreement; Strict
retains whole-image hash matching. This is visual similarity, not identity
verification, and every approximate match still needs review. Video samples use
the same features. Old descriptors are re-analyzed once for the new model.
See [subject matching](../../docs/subject-matching.md) for model provenance and thresholds.
