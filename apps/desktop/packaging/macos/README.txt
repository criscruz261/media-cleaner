Media Cleaner for macOS

Copy MediaCleaner.app to the destination Mac (for example, into Applications),
then double-click it. The interface opens in your default browser. Use Exit app
in the interface to stop the local server. Python and Node are bundled or are
not required; no media-tool downloads occur at runtime. ExifTool is optional
and is not included.

Build separately on Apple Silicon and Intel Macs. Use a destination with the
same CPU architecture and the same or a newer macOS version than the build Mac.
This app is locally ad-hoc signed, not Developer ID signed or notarized.
macOS may block transferred copies; use the macOS Privacy & Security Open Anyway
flow only if you trust the build. Public distribution needs signing/notarization
and testing on a clean destination Mac.

Library data is stored in ~/Library/Application Support/MediaCleaner, separate
from the application. Copying the app does not copy your library or media.
Build details and available third-party notices are in Contents/Resources.
