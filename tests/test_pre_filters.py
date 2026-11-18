# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Invariants of the pre-filters: size and value range are preserved,
# a flat image is left alone, and lighting flattening removes a
# vignette while keeping fine texture detail.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.PreFilters import (FILTERS, LIGHTING_WORK_SIZE,
                                              LightingFlatten, applyFilters,
                                              toUint8)

SIZE = 64


def checker(cell=4):
    """Fine detail: repeats SIZE / (2 * cell) times across the image."""
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    value = np.where(((x // cell) + (y // cell)) % 2 == 0, 160.0, 100.0)
    return np.repeat(value[..., None], 3, axis=2)


def vignette():
    """Bright centre, dark corners: 1.0 down to about 0.4."""
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    r2 = ((x - SIZE / 2) ** 2 + (y - SIZE / 2) ** 2) / (SIZE / 2) ** 2
    return (1.0 - 0.3 * r2)[..., None]


def cellMeans(array, cell=8):
    """Mean brightness per cell of one full checker period (2 x 4 px):
    hides the checker, shows the lighting."""
    gray = array.mean(axis=2)
    return gray.reshape(SIZE // cell, cell, SIZE // cell, cell).mean(axis=(1, 3))


class PreFilterInvariants(unittest.TestCase):

    def test_format_preserved_and_input_untouched(self):
        image = toUint8(checker() * vignette())
        frozen = image.copy()
        for prefilter in FILTERS:
            out = prefilter.apply(image)
            np.testing.assert_array_equal(image, frozen, prefilter.name)
            self.assertEqual(out.ndim, 3, prefilter.name)
            self.assertEqual(out.shape[2], 3, prefilter.name)
            self.assertEqual(out.dtype, np.uint8, prefilter.name)
            # A filter may crop, but never below half the size.
            self.assertGreaterEqual(out.shape[0] * 2, SIZE, prefilter.name)
            self.assertGreaterEqual(out.shape[1] * 2, SIZE, prefilter.name)

    def test_flat_image_unchanged(self):
        image = toUint8(np.full((SIZE, SIZE, 3), 120.0))
        for prefilter in FILTERS:
            np.testing.assert_array_equal(prefilter.apply(image), image,
                                          prefilter.name)

    def test_every_filter_is_described(self):
        for prefilter in FILTERS:
            self.assertGreater(len(prefilter.description), 40, prefilter.name)

    def test_no_filters_is_identity(self):
        image = toUint8(checker())
        self.assertIs(applyFilters(image, set()), image)


class LightingFlattenTest(unittest.TestCase):

    def test_removes_vignette(self):
        lit = checker() * vignette()
        out = LightingFlatten().apply(toUint8(lit)).astype(float)
        before = np.ptp(cellMeans(lit))
        after = np.ptp(cellMeans(out))
        self.assertLess(after, before * 0.1)

    def test_keeps_fine_detail(self):
        lit = checker() * vignette()
        out = LightingFlatten().apply(toUint8(lit)).astype(float)
        # Checker contrast between neighbouring cells survives.
        contrast = np.abs(out[:, 4:] - out[:, :-4]).mean()
        self.assertGreater(contrast, 0.7 * 60)

    def test_keeps_mean_brightness(self):
        lit = checker() * vignette()
        out = LightingFlatten().apply(toUint8(lit)).astype(float)
        self.assertAlmostEqual(out.mean(), lit.mean(), delta=1.0)

    def test_large_image_matches_full_resolution(self):
        """The downscaled lighting estimate gives the same picture as
        the exact full-resolution one."""
        size = 4 * LIGHTING_WORK_SIZE // 2 + 10    # odd-sized, downscaled
        y, x = np.mgrid[0:size, 0:size]
        cell = size // 40
        tex = np.where(((x // cell) + (y // cell)) % 2 == 0, 160.0, 100.0)
        light = 0.55 + 0.45 * x / (size - 1)
        lit = (tex * light)[..., None].repeat(3, axis=2)
        fast = LightingFlatten().apply(toUint8(lit)).astype(float)
        exact = LightingFlatten()._lighting(lit)
        exact = lit / exact
        exact *= lit.mean(axis=(0, 1)) / exact.mean(axis=(0, 1))
        self.assertLess(np.abs(fast - exact).mean(), 1.5)


if __name__ == '__main__':
    unittest.main()
