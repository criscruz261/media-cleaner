import tempfile
import unittest
from pathlib import Path

from app import scan_folder


class ScanTests(unittest.TestCase):
    def test_content_matches_across_names_and_subfolders(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nested').mkdir()
            (root / 'a.jpg').write_bytes(b'photo one')
            (root / 'nested' / 'renamed.PNG').write_bytes(b'photo one')
            (root / 'different.jpg').write_bytes(b'photo two')
            (root / 'ignore.txt').write_bytes(b'photo one')
            (root / 'link.jpg').symlink_to(root / 'a.jpg')
            result, files = scan_folder(directory)
            self.assertEqual(result['scanned'], 3)
            self.assertEqual(result['duplicates'], 1)
            self.assertEqual(result['recoverable'], 9)
            self.assertEqual(len(result['groups']), 1)
            self.assertEqual(len(files), 2)
            self.assertEqual(result['errors'], [])

    def test_empty_folder_and_invalid_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _ = scan_folder(directory)
            self.assertEqual(result['groups'], [])
            file = Path(directory) / 'file.jpg'
            file.touch()
            with self.assertRaises(ValueError):
                scan_folder(str(file))
            with self.assertRaises(FileNotFoundError):
                scan_folder(str(Path(directory) / 'missing'))


if __name__ == '__main__':
    unittest.main()
