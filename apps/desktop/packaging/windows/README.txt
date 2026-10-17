Media Cleaner - portable Windows package

Copy this ENTIRE folder, including _internal, to the destination Windows PC.
Double-click MediaCleaner.exe. Your default browser opens the local interface.
Keep the console window open while using the app. Use Exit app in the interface
or Ctrl+C in the console to stop it. No Python or Node.js installation is needed.

Requires Windows 10/11 and the same CPU architecture as the build machine.
The executable is unsigned. This is a portable folder, not an installer.
Normal operation is offline. ExifTool is optional and is not bundled.
Database, logs and settings are saved in your Windows local app-data directory,
not alongside the executable. Copying this package does not copy your library.

To verify the copied package from a terminal:
  .\MediaCleaner.exe --smoke-test
This uses a temporary database and does not scan or modify your media.

Third-party notices available from installed packages are in third-party-licenses.
FFmpeg/FFprobe come from setup's installed media tools. Their distribution and
codec license obligations must be reviewed before public redistribution.
