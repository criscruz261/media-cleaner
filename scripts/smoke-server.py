"""Temporary-only synthetic browser fixture server; never accepts real media paths."""
import json
from pathlib import Path
import secrets
import sys
import tempfile
from PIL import Image
import uvicorn
from app.api.main import create_app

with tempfile.TemporaryDirectory(prefix='media-cleaner-smoke-') as directory:
    root = Path(directory).resolve()
    media = root / 'synthetic-media'
    media.mkdir()
    Image.new('RGB', (320, 200), '#6d8c63').save(media / 'IMG_0971.png')
    (media / 'IMG_0971 copy.png').write_bytes((media / 'IMG_0971.png').read_bytes())
    token = secrets.token_urlsafe(32)
    config = {'media': str(media), 'token': token, 'port': 18765,
              'artifacts': str(Path(__file__).resolve().parents[1] / '.tools' / 'smoke-artifacts')}
    Path(sys.argv[1]).write_text(json.dumps(config))
    uvicorn.run(create_app(root / 'data', token=token), host='127.0.0.1', port=config['port'], access_log=False)
