Media Cleaner for Android — debug/testing build

Transfer media-cleaner-android-debug.apk to an Android 11+ device and open it.
Allow installation from your file manager when Android prompts, then grant the
app photo/video access. No desktop server, Python, Node, or account is needed.

This is a debug-signed APK, not a Play Store release. Updates require the same
signing key as the installed copy. Keep the build machine's debug key for future
updates. Uninstalling the app clears its private library data and checkpoints.

Verify the transferred APK on a computer with:
  shasum -a 256 -c media-cleaner-android-debug.apk.sha256
