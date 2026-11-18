# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Crop to whole repeats: a brick wall with a partial repeat is cut to
# whole repeats and then tiles cleanly, a running bond is cut to whole
# pairs of rows, pictures without a pattern (or already whole) are left
# alone, and the result is scaled back to the original size.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.PreFilters import PeriodCrop, resizePeriodic

BRICK, MORTAR = (170, 90, 70), (200, 200, 200)
PX, PY = 37, 23            # brick pitch along x and y, pixels


def wall(width, height, bond=False, seed=0):
    """Bricks with 4 px mortar; `bond` shifts every other row by half
    a brick (running bond: the y period becomes two rows)."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:height, 0:width]
    row = (y + 5) // PY
    shift = (row % 2) * (PX // 2) if bond else 0
    brick = ((x + 11 + shift) % PX < PX - 4) & ((y + 5) % PY < PY - 3)
    colors = np.where(brick[..., None], BRICK, MORTAR)
    return np.clip(colors + rng.normal(0, 6, colors.shape), 0, 255).astype(np.uint8)


def seamMismatch(image, axis, period):
    """How badly the pattern continues across the wrap: the window
    straddling the wrap of the tiled picture against the window one
    period before it. Pure noise (sigma 6, two copies) scores ~72."""
    lines = np.moveaxis(np.concatenate([image, image], axis=axis), axis, 0)
    lines = lines.astype(float)
    length, half = image.shape[axis], period // 2
    straddle = lines[length - half:length + half]
    before = lines[length - half - period:length + half - period]
    return ((straddle - before) ** 2).mean()


class PeriodCropTest(unittest.TestCase):

    def test_partial_repeat_is_cut_to_whole_repeats(self):
        out = PeriodCrop().crop(wall(200, 150))
        self.assertEqual(out.shape, (6 * PY, 5 * PX, 3))

    def test_result_keeps_size_and_tiles(self):
        image = wall(200, 150)
        out = PeriodCrop().apply(image)
        self.assertEqual(out.shape, image.shape)
        # Scaled by 200/185 and 150/138: the periods scale with it.
        px, py = round(PX * 200 / 185), round(PY * 150 / 138)
        self.assertLess(seamMismatch(out, 1, px), 300)
        self.assertLess(seamMismatch(out, 0, py), 300)

    def test_periodic_resize_keeps_wrap_continuous(self):
        tile = wall(5 * PX, 6 * PY)                # exactly whole repeats
        out = resizePeriodic(tile, 150, 200)
        self.assertEqual(out.shape, (150, 200, 3))
        self.assertLess(seamMismatch(out, 1, round(PX * 200 / 185)), 300)
        self.assertLess(seamMismatch(out, 0, round(PY * 150 / 138)), 300)

    def test_whole_repeats_left_alone(self):
        image = wall(5 * PX, 6 * PY)
        np.testing.assert_array_equal(PeriodCrop().apply(image), image)

    def test_running_bond_keeps_whole_row_pairs(self):
        out = PeriodCrop().crop(wall(200, 150, bond=True))
        self.assertEqual(out.shape, (6 * PY, 5 * PX, 3))     # 6 rows = 3 pairs
        self.assertLess(seamMismatch(out, 0, 2 * PY), 200)
        self.assertLess(seamMismatch(out, 1, PX), 200)

    def test_cropped_wall_tiles_better_than_original(self):
        image = wall(200, 150)
        out = PeriodCrop().crop(image)
        for axis, period in ((0, PY), (1, PX)):
            self.assertGreater(seamMismatch(image, axis, period), 800, axis)
            self.assertLess(seamMismatch(out, axis, period), 200, axis)

    def test_noise_and_flat_untouched(self):
        rng = np.random.default_rng(1)
        for image in [rng.integers(0, 256, (150, 200, 3), dtype=np.uint8),
                      np.full((150, 200, 3), 120, dtype=np.uint8)]:
            np.testing.assert_array_equal(PeriodCrop().apply(image), image)

    def test_never_below_half(self):
        # One brick fits 1.9 times: keeps one whole brick, not less.
        image = wall(int(PX * 1.9), int(PY * 1.9))
        out = PeriodCrop().crop(image)
        self.assertGreaterEqual(out.shape[0] * 2, image.shape[0])
        self.assertGreaterEqual(out.shape[1] * 2, image.shape[1])
        self.assertEqual(out.shape[:2], (PY, PX))

    def test_tiny_image_untouched(self):
        image = wall(12, 10)
        np.testing.assert_array_equal(PeriodCrop().apply(image), image)


if __name__ == '__main__':
    unittest.main()
