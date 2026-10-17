"""Frozen Windows entry point; no installed Python/Node or runtime downloads."""
import argparse
import multiprocessing
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Media Cleaner portable Windows app")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    resources = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    for name in ("ffmpeg", "ffprobe"):
        os.environ["MEDIA_CLEANER_" + name.upper()] = str(resources / "media-tools" / (name + ".exe"))
    from app.api.main import create_app
    from app.core.config import authentication_token, data_directory
    import uvicorn

    temporary = tempfile.TemporaryDirectory(prefix="media-cleaner-smoke-") if args.smoke_test else None
    directory = Path(temporary.name) if temporary else (args.data_dir or data_directory())
    directory.mkdir(parents=True, exist_ok=True)
    token = authentication_token(directory)
    application = create_app(directory, token=token, frontend=resources / "frontend")
    # Reserve the port until Uvicorn takes over, avoiding collisions with other apps.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, access_log=False))
        application.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
        failures = []

        def ready():
            try:
                deadline = time.monotonic() + 60
                while not server.started:
                    if time.monotonic() > deadline or server.should_exit:
                        raise RuntimeError("Local server did not start")
                    time.sleep(0.1)
                url = f"http://127.0.0.1:{port}/"
                if args.smoke_test:
                    with urllib.request.urlopen(url, timeout=10) as response:
                        assert response.status == 200 and b"<html" in response.read().lower()
                    request = urllib.request.Request(url + "api/v1/settings", headers={"Authorization": f"Bearer {token}"})
                    with urllib.request.urlopen(request, timeout=10) as response:
                        assert response.status == 200
                    for name in ("ffmpeg", "ffprobe"):
                        subprocess.run([os.environ["MEDIA_CLEANER_" + name.upper()], "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=20)
                else:
                    webbrowser.open(url + "#token=" + token)
                    print("Media Cleaner is running in your browser. Keep this window open.")
                    print("Use Exit app in the interface, or Ctrl+C here, to stop.", flush=True)
            except Exception as exc:
                failures.append(exc)
            finally:
                if args.smoke_test or failures:
                    server.should_exit = True

        thread = threading.Thread(target=ready, daemon=True)
        thread.start()
        try:
            server.run(sockets=[listener])
            thread.join(timeout=65)
            if thread.is_alive():
                raise RuntimeError("Startup verification timed out")
            if failures:
                raise failures[0]
        finally:
            if temporary:
                temporary.cleanup()
    if args.smoke_test:
        print("Portable smoke test passed: UI, API, migrations, FFmpeg and FFprobe.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
