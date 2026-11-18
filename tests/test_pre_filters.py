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

from modules.TextureEditor.PreFilters import (FILTERS, LightingFlatten,
                                              applyFilters, arrayToGrid,
                                              gridToArray)

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

    def test_size_and_range_preserved(self):
        grid = arrayToGrid(checker() * vignette())
        for prefilter in FILTERS:
            out = prefilter.apply(grid)
            self.assertEqual(len(out), SIZE, prefilter.name)
            self.assertEqual(len(out[0]), SIZE, prefilter.name)
            values = np.asarray(out)
            self.assertTrue(values.min() >= 0 and values.max() <= 255)

    def test_flat_image_unchanged(self):
        grid = arrayToGrid(np.full((SIZE, SIZE, 3), 120.0))
        for prefilter in FILTERS:
            self.assertEqual(prefilter.apply(grid), grid, prefilter.name)

    def test_every_filter_is_described(self):
        for prefilter in FILTERS:
            self.assertGreater(len(prefilter.description), 40, prefilter.name)

    def test_no_filters_is_identity(self):
        grid = arrayToGrid(checker())
        self.assertIs(applyFilters(grid, set()), grid)


class LightingFlattenTest(unittest.TestCase):

    def test_removes_vignette(self):
        lit = checker() * vignette()
        out = gridToArray(LightingFlatten().apply(arrayToGrid(lit)))
        before = np.ptp(cellMeans(lit))
        after = np.ptp(cellMeans(out))
        self.assertLess(after, before * 0.1)

    def test_keeps_fine_detail(self):
        lit = checker() * vignette()
        out = gridToArray(LightingFlatten().apply(arrayToGrid(lit)))
        # Checker contrast between neighbouring cells survives.
        contrast = np.abs(out[:, 4:] - out[:, :-4]).mean()
        self.assertGreater(contrast, 0.7 * 60)

    def test_keeps_mean_brightness(self):
        lit = checker() * vignette()
        out = gridToArray(LightingFlatten().apply(arrayToGrid(lit)))
        self.assertAlmostEqual(out.mean(), lit.mean(), delta=1.0)


if __name__ == '__main__':
    unittest.main()
