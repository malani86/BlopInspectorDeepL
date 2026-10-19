import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from backend import create_run_directory
from file_io import read_image_unicode, save_image_unicode
from labeling import save_label_maps, load_label_map, measure_droplet_labels
from spatial_analysis import analyze_spatial, export_spatial


class OutputTests(unittest.TestCase):
    def test_unicode_outputs_and_spatial_reopen(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / '6µM échantillon تجربة'
            mask = np.zeros((32, 32), np.uint8)
            mask[10:14, 10:14] = 255
            source = np.repeat(mask[..., None], 3, axis=2)
            for name, image in [('mask.png', mask), ('source.png', source)]:
                save_image_unicode(directory / name, image)
                actual = read_image_unicode(directory / name, cv2.IMREAD_UNCHANGED)
                np.testing.assert_array_equal(actual, image)
            labels = (mask > 0).astype(np.int32)
            save_label_maps(directory, '6µM', labels)
            np.testing.assert_array_equal(load_label_map(directory, '6µM', mask), labels)
            table = measure_droplet_labels(labels, 5)
            table.to_csv(directory / 'droplets.csv', index=False)
            result = analyze_spatial(mask, table, np.ones_like(mask, dtype=bool))
            export_spatial(directory / 'spatial', result, mask, source)
            np.testing.assert_array_equal(
                read_image_unicode(directory / 'spatial/region_mask.png', 0),
                np.full_like(mask, 255))
            self.assertTrue((directory / 'spatial/spatial_summary.csv').is_file())

    def test_failed_replace_preserves_previous_image(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'mask.png'
            original = np.zeros((4, 4), np.uint8)
            save_image_unicode(path, original)
            with patch('file_io.os.replace', side_effect=PermissionError('locked')):
                with self.assertRaisesRegex(OSError, 'mask.png'):
                    save_image_unicode(path, original + 255)
            np.testing.assert_array_equal(read_image_unicode(path, 0), original)
            self.assertEqual(list(Path(root).iterdir()), [path])

    def test_unique_short_writable_run_folders(self):
        with tempfile.TemporaryDirectory() as root:
            first = create_run_directory(root)
            second = create_run_directory(root)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_absolute() and first.is_dir() and second.is_dir())
            self.assertEqual(len(list(Path(root).iterdir())), 2)
            self.assertIsNone(read_image_unicode(first / 'missing.png'))


if __name__ == '__main__':
    unittest.main()
