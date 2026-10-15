"""Local-only similar photo and duplicate finder."""
import argparse
import hashlib
import json
import mimetypes
import os
import re
import secrets
import threading
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PHOTO_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.heic', '.heif', '.avif', '.dng', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2'}
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.m4v', '.avi', '.mkv', '.webm', '.mts', '.m2ts', '.insv', '.lrv'}
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS
STATIC = Path(__file__).parent / 'static'


def preferred_keeper(files):
    def rank(file):
        stem = Path(file['name']).stem
        copy_marker = re.search(r'(?:^|[\s_-])(?:copy|duplicate)(?=$|[\s_()\d-])|\s*\(\d+\)$', stem, re.IGNORECASE)
        return (bool(copy_marker), -file['size'], file['path'].casefold(), file['path'])
    return min(files, key=rank)['id']


def visual_fingerprint(path):
    from PIL import Image, ImageOps
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('L').resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(image.getdata())
        fingerprint = 0
        for y in range(8):
            for x in range(8):
                fingerprint = (fingerprint << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
        return fingerprint


def scan_folder(directory, progress=None, mode='exact', threshold=6):
    if mode not in {'exact', 'similar'}:
        raise ValueError('Choose exact or similar matching.')
    if mode == 'similar':
        try:
            import PIL
        except ImportError:
            raise ValueError('Similar matching requires Pillow. Install requirements.txt and restart the app.')
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
                elif path.suffix.lower() in MEDIA_EXTENSIONS and path.is_file():
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
    if mode == 'similar':
        # Keep exact matches (including formats Pillow cannot decode), then merge
        # visual matches around a fixed representative to avoid similarity chains.
        exact_groups = groups
        groups = []
        for group in exact_groups:
            if any(Path(file['path']).suffix.lower() in VIDEO_EXTENSIONS for file in group['files']):
                group['kind'] = 'exact'
                for file in group['files']:
                    file['size'] = group['size']
                groups.append(group)
        representatives = []
        exact_by_path = {file['path']: group for group in exact_groups for file in group['files']}
        visited = {file['path'] for group in groups for file in group['files']}
        paths = sorted(path for bucket in buckets.values() for path in bucket
                       if path.suffix.lower() in PHOTO_EXTENSIONS)
        for number, path in enumerate(paths, 1):
            if progress:
                progress(phase='similarity', compared=number, candidates=len(paths))
            if str(path) in visited:
                continue
            exact = exact_by_path.get(str(path))
            members = [Path(file['path']) for file in exact['files']] if exact else [path]
            visited.update(str(member) for member in members)
            try:
                fingerprint = visual_fingerprint(path)
            except Exception as exc:
                errors.append(f'{path}: Visual comparison unavailable: {exc}')
                fingerprint = None
            target = None
            if fingerprint is not None:
                for representative, candidate in representatives:
                    if bin(fingerprint ^ representative).count('1') <= threshold:
                        target = candidate
                        break
            if target is None:
                target = {'kind': 'similar', 'files': []}
                groups.append(target)
                if fingerprint is not None:
                    representatives.append((fingerprint, target))
            for member in members:
                try:
                    size = member.stat().st_size
                except OSError as exc:
                    errors.append(f'{member}: {exc}')
                    continue
                token = secrets.token_urlsafe(18)
                files[token] = member
                target['files'].append({'id': token, 'name': member.name, 'path': str(member),
                                        'relative': str(member.relative_to(root)), 'size': size})
        groups = [group for group in groups if len(group['files']) > 1]
        for group in groups:
            sizes = [file['size'] for file in group['files']]
            group['recoverable'] = sum(sizes) - max(sizes)
    else:
        for group in groups:
            group['kind'] = 'exact'
            for file in group['files']:
                file['size'] = group['size']
    for group in groups:
        for file in group['files']:
            file['media_type'] = 'video' if Path(file['path']).suffix.lower() in VIDEO_EXTENSIONS else 'photo'
        group['preferred_keeper'] = preferred_keeper(group['files'])
    groups.sort(key=lambda group: group['recoverable'], reverse=True)
    return {'folder': str(root), 'mode': mode, 'scanned': count, 'totalBytes': total_bytes, 'groups': groups,
            'duplicates': sum(len(group['files']) - 1 for group in groups),
            'recoverable': sum(group['recoverable'] for group in groups), 'errors': errors}, files


def file_identity(path):
    if path.is_symlink() or path.resolve(strict=True) != path:
        raise ValueError(f'Path changed or contains a symlink: {path}. Scan again.')
    info = path.stat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def delete_selected(result, files, identities, ids):
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) for item in ids):
        raise ValueError('Select files to delete.')
    requested = set(ids)
    grouped = {file['id'] for group in result['groups'] for file in group['files']}
    if len(requested) != len(ids) or not requested <= grouped:
        raise ValueError('Invalid or stale selection. Scan again.')
    for group in result['groups']:
        if all(file['id'] in requested for file in group['files']):
            raise ValueError('Keep at least one file in every group.')
    # Check retained files too, so a missing keeper blocks removal of its copies.
    for group in result['groups']:
        if not any(file['id'] in requested for file in group['files']):
            continue
        for file in group['files']:
            token = file['id']
            if file_identity(files[token]) != identities.get(token):
                raise ValueError(f"File changed since scanning: {file['path']}. Scan again.")
    deleted, errors = [], []
    for token in ids:
        path = files[token]
        try:
            if file_identity(path) != identities[token]:
                raise ValueError('File changed since scanning.')
            path.unlink()
            deleted.append(str(path))
        except (OSError, ValueError) as exc:
            errors.append(f'{path}: {exc}')
    return {'deleted': deleted, 'errors': errors}


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
                with path.open('rb') as source:
                    size = os.fstat(source.fileno()).st_size
                    start, end = 0, size - 1
                    byte_range = self.headers.get('Range')
                    if byte_range:
                        match = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range.strip())
                        try:
                            if not match or not any(match.groups()) or not size:
                                raise ValueError()
                            first, last = match.groups()
                            if first:
                                start = int(first)
                                end = min(int(last), size - 1) if last else size - 1
                            else:
                                suffix = int(last)
                                if suffix <= 0:
                                    raise ValueError()
                                start = max(0, size - suffix)
                            if start >= size or start > end:
                                raise ValueError()
                        except ValueError:
                            self.send_response(416)
                            self.send_header('Content-Range', f'bytes */{size}')
                            self.send_header('Content-Length', '0')
                            self.end_headers()
                            return
                    self.send_response(206 if byte_range else 200)
                    self.send_header('Accept-Ranges', 'bytes')
                    if byte_range:
                        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                    self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                    self.send_header('Content-Length', str(end - start + 1))
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    try:
                        source.seek(start)
                        remaining = end - start + 1
                        while remaining > 0:
                            chunk = source.read(min(1024 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                return
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
        if self.path == '/api/delete':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError('Invalid request size.')
                request = json.loads(self.rfile.read(length))
                with self.server.lock:
                    state = self.server.state
                    if (state['status'] != 'done' or request.get('confirmed') is not True
                            or not secrets.compare_digest(str(request.get('delete_token', '')), state['result']['delete_token'])):
                        raise ValueError('Confirmation is required for the current scan.')
                    outcome = delete_selected(state['result'], self.server.files, self.server.identities, request.get('ids'))
                    deleted = set(outcome['deleted'])
                    result = state['result']
                    for group in result['groups']:
                        group['files'] = [file for file in group['files'] if file['path'] not in deleted]
                        sizes = [file['size'] for file in group['files']]
                        group['recoverable'] = sum(sizes) - max(sizes, default=0)
                        if group['files']:
                            group['preferred_keeper'] = preferred_keeper(group['files'])
                    result['groups'] = [group for group in result['groups'] if len(group['files']) > 1]
                    result['duplicates'] = sum(len(group['files']) - 1 for group in result['groups'])
                    result['recoverable'] = sum(group['recoverable'] for group in result['groups'])
                    result['delete_token'] = secrets.token_urlsafe(32)
                    remaining = {file['id'] for group in result['groups'] for file in group['files']}
                    self.server.files = {token: path for token, path in self.server.files.items() if token in remaining}
                    self.server.identities = {token: identity for token, identity in self.server.identities.items() if token in remaining}
                    outcome['result'] = result
                return self.reply(200, outcome)
            except (ValueError, OSError, TypeError, AttributeError) as exc:
                return self.reply(400, {'error': str(exc)})
        if self.path != '/api/scan':
            return self.reply(404, {'error': 'Not found.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError('Invalid request size.')
            request = json.loads(self.rfile.read(length))
            directory = request.get('directory', '')
            mode = request.get('mode', 'similar')
            if mode not in {'exact', 'similar'}:
                raise ValueError('Choose exact or similar matching.')
            if mode == 'similar':
                try:
                    import PIL
                except ImportError:
                    raise ValueError('Similar matching requires Pillow. Install requirements.txt and restart the app.')
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
                result, files = scan_folder(str(root), progress, mode=mode)
                identities = {file['id']: file_identity(files[file['id']]) for group in result['groups'] for file in group['files']}
                result['delete_token'] = secrets.token_urlsafe(32)
                with self.server.lock:
                    self.server.identities = identities
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
