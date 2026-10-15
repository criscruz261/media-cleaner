import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import scan_folder


class VideoTests(unittest.TestCase):
    def make_collection(self, root):
        (root / 'nested').mkdir()
        (root / 'IMG_0971.MOV').write_bytes(b'video one')
        (root / 'nested' / 'IMG_0971 copy.mov').write_bytes(b'video one')
        (root / 'different.MOV').write_bytes(b'video two')
        (root / 'VID.mp4').write_bytes(b'other video')
        (root / 'renamed.MP4').write_bytes(b'other video')
        (root / 'clip.insv').write_bytes(b'360 video')
        (root / 'nested' / 'clip copy.INSV').write_bytes(b'360 video')
        (root / 'clip.lrv').write_bytes(b'preview')
        (root / 'clip copy.LRV').write_bytes(b'preview')
        (root / 'link.mov').symlink_to(root / 'IMG_0971.MOV')

    def assert_videos(self, result):
        self.assertEqual(result['scanned'], 9)
        self.assertEqual(len(result['groups']), 4)
        self.assertEqual(result['duplicates'], 4)
        self.assertEqual(result['errors'], [])
        for group in result['groups']:
            self.assertEqual(group['kind'], 'exact')
            self.assertTrue(all(file['media_type'] == 'video' for file in group['files']))

    def test_exact_videos_in_nested_folders(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_collection(Path(directory))
            result, _ = scan_folder(directory)
            self.assert_videos(result)

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'Pillow required')
    def test_similar_mode_keeps_exact_videos_without_image_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            self.make_collection(Path(directory))
            with patch('app.visual_fingerprint', side_effect=AssertionError('Video sent to image decoder')) as fingerprint:
                result, _ = scan_folder(directory, mode='similar')
            fingerprint.assert_not_called()
            self.assert_videos(result)
