# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Suppress highlights: glare spots on a brick wall are blended away
# while the wall itself, including its bright mortar, is left alone,
# and a mostly white picture is not treated as glare.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.PreFilters import HighlightSuppress
from test_period_crop import wall

SPOTS = [(40, 60, 6), (110, 150, 9), (20, 180, 4)]     # (y, x, radius)


def glare(image, spots=SPOTS):
    """Bright spots with soft edges added to a copy of the wall."""
    out = image.astype(float)
    y, x = np.mgrid[0:image.shape[0], 0:image.shape[1]]
    for cy, cx, r in spots:
        spot = np.exp(-((y - cy) ** 2 + (x - cx) ** 2) / (2 * (r / 2.0) ** 2))
        out += 230 * spot[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def luminance(image):
    return image.astype(float) @ [0.299, 0.587, 0.114]


def spotMask(shape, spots=SPOTS):
    y, x = np.mgrid[0:shape[0], 0:shape[1]]
    mask = np.zeros(shape[:2], bool)
    for cy, cx, r in spots:
        mask |= (y - cy) ** 2 + (x - cx) ** 2 <= r ** 2
    return mask


class HighlightSuppressTest(unittest.TestCase):

    def test_glare_spots_are_removed(self):
        """Brightness excess over the clean wall inside the spots. (The
        fill is a smooth colour, so pixel-exact texture is not expected
        back: this measures the glare, not the mortar lines under it.)"""
        clean = wall(200, 150)
        lit = glare(clean)
        out = HighlightSuppress().apply(lit)
        mask = spotMask(clean.shape)
        before = (luminance(lit) - luminance(clean))[mask].mean()
        after = (luminance(out) - luminance(clean))[mask].mean()
        self.assertGreater(before, 60)
        self.assertLess(abs(after), 12)
        # No bright ring left at any distance from a spot centre.
        y, x = np.mgrid[0:150, 0:200]
        distance = np.sqrt((y - 120) ** 2 + (x - 150) ** 2)
        excess = luminance(out) - luminance(clean)
        for r in range(0, 14):
            ring = (distance >= r) & (distance < r + 1)
            self.assertLess(abs(excess[ring].mean()), 25, r)

    def test_wall_without_glare_untouched(self):
        clean = wall(200, 150)
        np.testing.assert_array_equal(HighlightSuppress().apply(clean), clean)

    def test_stray_bright_pixels_are_not_glare(self):
        clean = wall(200, 150)
        rng = np.random.default_rng(5)
        for _ in range(30):                        # bright grains, far apart
            y, x = rng.integers(0, 150), rng.integers(0, 200)
            clean[y, x] = 252
        np.testing.assert_array_equal(HighlightSuppress().apply(clean), clean)

    def test_outside_the_spots_untouched(self):
        clean = wall(200, 150)
        lit = glare(clean)
        out = HighlightSuppress().apply(lit)
        far = ~spotMask(clean.shape, [(y, x, 4 * r) for y, x, r in SPOTS])
        np.testing.assert_array_equal(out[far], lit[far])

    def test_white_surface_is_not_glare(self):
        image = np.full((150, 200, 3), 245, dtype=np.uint8)
        image[::7] = 230                               # some structure
        np.testing.assert_array_equal(HighlightSuppress().apply(image), image)

    def test_noise_mostly_untouched(self):
        rng = np.random.default_rng(3)
        image = rng.integers(0, 256, (150, 200, 3), dtype=np.uint8)
        out = HighlightSuppress().apply(image)
        self.assertLess(np.any(out != image, axis=2).mean(), 0.05)


if __name__ == '__main__':
    unittest.main()
