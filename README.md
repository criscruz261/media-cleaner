# PhotoFold

A fully local, read-only photo duplicate finder with a browser interface. Requires Python 3.10+; no packages, accounts, internet connection, or build step needed.

```bash
./run.sh
```

The launcher works from any working directory and checks for Python 3.10+. Alternatively, run `python3 app.py`; on Windows, use `py app.py`. Open **http://127.0.0.1:8765**, paste an absolute folder path (for example `/home/you/Pictures`, `C:\Users\you\Pictures`, or `~/Pictures`), and click **Scan for duplicates**. Subfolders are included. To use another port: `./run.sh --port 9000`. Stop with Ctrl+C.

PhotoFold compares file sizes, then streams matching-size files through SHA-256. It detects byte-for-byte identical copies even when names differ. Resized, edited, recompressed, or visually similar images are not considered duplicates. Supported extensions include JPEG, PNG, GIF, WebP, BMP, TIFF, HEIC/HEIF, AVIF, and common camera RAW formats. Browser preview support varies; unsupported images still participate in duplicate detection.

Results show duplicate groups, full paths, extra copies, and potential space savings. Export a JSON report for manual cleanup. Nothing is deleted, moved, or modified. Symlinks are skipped; unreadable files and folders are listed in the result. Do not modify a collection during a scan. Scanning very large collections can take time; scan progress updates automatically.

The server binds only to IPv4 loopback (`127.0.0.1`). Photos, paths, and reports remain on your computer. All fonts, scripts, and styles are local; there are no analytics, CDNs, uploads, or outbound network requests. Results are held in memory until the next scan or server shutdown. Anyone with access to your local computer/browser can access this local app; it is not intended to be exposed to a network or reverse proxy. Previewing a photo loads it into browser memory.

Run checks with `python3 -m unittest discover -s tests -v`.
