"""Local-only photo duplicate finder. No third-party dependencies."""
import argparse
import hashlib
import json
import mimetypes
import secrets
import threading
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.heic', '.heif', '.avif', '.dng', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2'}
STATIC = Path(__file__).parent / 'static'


def scan_folder(directory, progress=None):
    root = Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Please enter a folder, rather than a file.')
    buckets = defaultdict(list)
    errors = []
    count = 0
    total_bytes = 0

    def walk(folder):
        nonlocal count, total_bytes
        try:
            for path in folder.iterdir():
                if path.is_symlink():
                    continue
                if path.is_dir():
                    walk(path)
                elif path.suffix.lower() in PHOTO_EXTENSIONS and path.is_file():
                    try:
                        size = path.stat().st_size
                        buckets[size].append(path)
                        count += 1
                        total_bytes += size
                        if progress:
                            progress(phase='discovering', scanned=count)
                    except OSError as exc:
                        errors.append(f'{path}: {exc}')
        except OSError as exc:
            errors.append(f'{folder}: {exc}')

    walk(root)
    groups = []
    files = {}
    candidates = sum(len(paths) for paths in buckets.values() if len(paths) > 1)
    hashed = 0
    for size, paths in buckets.items():
        if len(paths) < 2:
            continue
        digests = defaultdict(list)
        for path in paths:
            try:
                before = path.stat()
                digest = hashlib.sha256()
                with path.open('rb') as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        digest.update(chunk)
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise OSError('File changed during scanning; scan again.')
                digests[digest.hexdigest()].append(path)
            except OSError as exc:
                errors.append(f'{path}: {exc}')
            hashed += 1
            if progress:
                progress(phase='hashing', scanned=count, hashed=hashed, candidates=candidates)
        for digest, matches in digests.items():
            if len(matches) < 2:
                continue
            members = []
            for path in sorted(matches):
                token = secrets.token_urlsafe(18)
                files[token] = path
                members.append({'id': token, 'name': path.name, 'path': str(path), 'relative': str(path.relative_to(root))})
            groups.append({'hash': digest, 'size': size, 'recoverable': size * (len(matches) - 1), 'files': members})
    groups.sort(key=lambda group: group['recoverable'], reverse=True)
    return {'folder': str(root), 'scanned': count, 'totalBytes': total_bytes, 'groups': groups,
            'duplicates': sum(len(group['files']) - 1 for group in groups),
            'recoverable': sum(group['recoverable'] for group in groups), 'errors': errors}, files


class AppServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.lock = threading.Lock()
        self.state = {'status': 'idle'}
        self.files = {}


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data, content_type='application/json'):
        payload = json.dumps(data).encode() if content_type == 'application/json' else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)

    def allowed_host(self):
        return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

    def do_GET(self):
        if not self.allowed_host():
            return self.reply(403, {'error': 'Local access only.'})
        parsed = urlparse(self.path)
        if parsed.path == '/api/status':
            with self.server.lock:
                return self.reply(200, self.server.state)
        if parsed.path == '/api/photo':
            token = parse_qs(parsed.query).get('id', [''])[0]
            with self.server.lock:
                path = self.server.files.get(token)
            if not path or path.is_symlink():
                return self.reply(404, {'error': 'Photo unavailable.'})
            try:
                return self.reply(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            except OSError:
                return self.reply(404, {'error': 'Photo unavailable.'})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css'), '/app.js': ('app.js', 'text/javascript')}
        if parsed.path not in assets:
            return self.reply(404, {'error': 'Not found.'})
        name, mime = assets[parsed.path]
        self.reply(200, (STATIC / name).read_bytes(), mime)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if not self.allowed_host() or origin not in {None, f'http://{self.headers.get("Host")}'} or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.reply(403, {'error': 'Local access only.'})
        if self.path != '/api/scan':
            return self.reply(404, {'error': 'Not found.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size.')
            directory = json.loads(self.rfile.read(length)).get('directory', '')
            if not isinstance(directory, str) or not directory.strip():
                raise ValueError('Enter a folder path to scan.')
            root = Path(directory).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError('Please enter a folder, rather than a file.')
        except (ValueError, OSError) as exc:
            return self.reply(400, {'error': str(exc)})
        with self.server.lock:
            if self.server.state['status'] == 'scanning':
                return self.reply(409, {'error': 'A scan is already running.'})
            self.server.state = {'status': 'scanning', 'phase': 'discovering', 'scanned': 0}
            self.server.files = {}

        def run():
            def progress(**values):
                with self.server.lock:
                    self.server.state.update(values)
            try:
                result, files = scan_folder(str(root), progress)
                with self.server.lock:
                    self.server.files = files
                    self.server.state = {'status': 'done', 'result': result}
            except Exception as exc:
                with self.server.lock:
                    self.server.state = {'status': 'error', 'error': str(exc)}
        threading.Thread(target=run, daemon=True).start()
        self.reply(202, {'status': 'scanning'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = AppServer(('127.0.0.1', args.port))
    print(f'PhotoFold is running locally at http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
