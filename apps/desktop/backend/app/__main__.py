import argparse
from pathlib import Path
import uvicorn
from app.core.config import data_directory, authentication_token
from app.api.main import create_app


def main():
    parser = argparse.ArgumentParser(description="Media Cleaner · local media workspace")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    directory = (args.data_dir or data_directory()).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    token = authentication_token(directory)
    application = create_app(directory, token=token)
    print(f"Open http://127.0.0.1:{args.port}/#token={token}", flush=True)
    print("The launch token grants access to your local library. Keep this link private.", flush=True)
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=args.port, access_log=False))
    application.state.shutdown_callback = lambda: setattr(server, "should_exit", True)
    server.run()


if __name__ == "__main__":
    main()
