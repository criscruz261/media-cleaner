import tempfile
import unittest
from pathlib import Path

from app import scan_folder

try:
    from PIL import Image
except ImportError:
    Image = None


@unittest.skipIf(Image is None, 'Pillow required')
class SimilarityTests(unittest.TestCase):
    def test_resized_photo_matches_but_opposite_gradient_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = Image.new('RGB', (90, 80))
            image.putdata([(x * 2, y * 3, x * 2) for y in range(80) for x in range(90)])
            image.save(root / 'original.png')
            image.resize((45, 40)).save(root / 'resized.png')
            image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(root / 'different.png')
            exact, _ = scan_folder(directory)
            self.assertEqual(exact['groups'], [])
            similar, files = scan_folder(directory, mode='similar')
            self.assertEqual(len(similar['groups']), 1)
            group = similar['groups'][0]
            self.assertEqual({f['name'] for f in group['files']}, {'original.png', 'resized.png'})
            self.assertTrue(all(f['id'] in files and f['size'] > 0 for f in group['files']))

    def test_unsupported_images_preserve_exact_matches_and_report_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'one.heic').write_bytes(b'unsupported photo')
            (root / 'two.heic').write_bytes(b'unsupported photo')
            result, _ = scan_folder(directory, mode='similar')
            self.assertEqual(len(result['groups']), 1)
            self.assertEqual(result['duplicates'], 1)
            self.assertTrue(result['errors'])

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            scan_folder('.', mode='invalid')
