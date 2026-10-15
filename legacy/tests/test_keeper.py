import unittest

from app import preferred_keeper


class KeeperTests(unittest.TestCase):
    def choose(self, names):
        return preferred_keeper([{'id': name, 'name': name, 'path': '/photos/' + name, 'size': size} for name, size in names])

    def test_original_preferred_over_copy_even_if_copy_larger(self):
        for copy in ['IMG_0971 copy.MOV', 'IMG_0971 COPY 2.MOV', 'IMG_0971 (1).MOV', 'IMG_0971-duplicate.MOV', 'Copy of IMG_0971.MOV']:
            with self.subTest(copy=copy):
                self.assertEqual(self.choose([(copy, 200), ('IMG_0971.MOV', 100)]), 'IMG_0971.MOV')

    def test_camera_number_not_treated_as_copy(self):
        self.assertEqual(self.choose([('IMG_0971.MOV', 200), ('holiday.MOV', 100)]), 'IMG_0971.MOV')

    def test_deterministic_tie_and_unmarked_word(self):
        self.assertEqual(self.choose([('b.jpg', 100), ('a.jpg', 100)]), 'a.jpg')
        self.assertEqual(self.choose([('copyright.jpg', 200), ('a.jpg', 100)]), 'copyright.jpg')
