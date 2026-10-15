import io
import tempfile
import threading
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app import Handler


class PreviewTests(unittest.TestCase):
    def request(self, path, byte_range=None):
        handler = Handler.__new__(Handler)
        handler.path = '/api/photo?id=test'
        handler.headers = Message()
        handler.headers['Host'] = '127.0.0.1:8765'
        if byte_range is not None:
            handler.headers['Range'] = byte_range
        handler.server = SimpleNamespace(server_port=8765, files={'test': path}, lock=threading.Lock())
        handler.wfile = io.BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.do_GET()
        return handler

    def test_full_and_partial_media(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.MOV'
            path.write_bytes(b'0123456789')
            for byte_range, status, expected in [(None, 200, b'0123456789'), ('bytes=0-1', 206, b'01'), ('bytes=5-', 206, b'56789'), ('bytes=-3', 206, b'789'), ('bytes=8-99', 206, b'89')]:
                with self.subTest(byte_range=byte_range):
                    handler = self.request(path, byte_range)
                    handler.send_response.assert_called_once_with(status)
                    self.assertEqual(handler.wfile.getvalue(), expected)
                    handler.send_header.assert_any_call('Content-Length', str(len(expected)))
                    handler.send_header.assert_any_call('Accept-Ranges', 'bytes')

    def test_invalid_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'clip.mp4'
            path.write_bytes(b'0123456789')
            for byte_range in ['bytes=10-', 'bytes=5-2', 'bytes=-0', 'bytes=-', 'bytes=0-1,4-5', 'bad']:
                with self.subTest(byte_range=byte_range):
                    handler = self.request(path, byte_range)
                    handler.send_response.assert_called_once_with(416)
                    handler.send_header.assert_any_call('Content-Range', 'bytes */10')
                    self.assertEqual(handler.wfile.getvalue(), b'')

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'empty.mov'
            path.touch()
            handler = self.request(path)
            handler.send_response.assert_called_once_with(200)
            handler.send_header.assert_any_call('Content-Length', '0')
            self.request(path, 'bytes=0-').send_response.assert_called_once_with(416)
