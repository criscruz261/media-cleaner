"""Install a verified Node 22 archive into the project (development only)."""
import hashlib
import platform
from pathlib import Path
import tarfile
import urllib.request

root = Path(__file__).resolve().parents[1] / '.tools'
root.mkdir(exist_ok=True)
system = {'Darwin': 'darwin', 'Linux': 'linux'}[platform.system()]
arch = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64'}[platform.machine()]
base = 'https://nodejs.org/dist/latest-v22.x/'
checks = urllib.request.urlopen(base + 'SHASUMS256.txt').read().decode()
checksum, name = next(line.split() for line in checks.splitlines() if line.endswith(f'-{system}-{arch}.tar.gz'))
archive = root / name
urllib.request.urlretrieve(base + name, archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
    raise RuntimeError('Node archive checksum mismatch')
with tarfile.open(archive) as source:
    for member in source.getmembers():
        if not (root / member.name).resolve().is_relative_to(root.resolve()):
            raise RuntimeError('Unsafe archive member')
    source.extractall(root, filter='data')
print(root / name.removesuffix('.tar.gz') / 'bin')
