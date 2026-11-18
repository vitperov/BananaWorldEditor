# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Invariants of the seamless-texture algorithms: size and value range
# are preserved, the conversion is a pure function, and the wrap seam
# of the result is far smaller than the seam of a worst-case input.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.SeamlessAlgorithms import (ALGORITHMS,
                                                      algorithmByName)


def gradient(width, height):
    """Horizontal+vertical gradient: the least tileable image there is."""
    y, x = np.mgrid[0:height, 0:width]
    return np.stack([255 * x // (width - 1), 255 * y // (height - 1),
                     np.full_like(x, 128)], axis=-1).astype(np.uint8)


def noisy(width, height, seed=7):
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


def seamJump(pixels):
    """Mean channel difference across the tile wrap, both axes."""
    p = pixels.astype(int)
    jumps = np.concatenate([np.abs(p[:, 0] - p[:, -1]).ravel(),
                            np.abs(p[0] - p[-1]).ravel()])
    return jumps.mean()


class SeamlessAlgorithms(unittest.TestCase):

    def test_size_range_and_purity(self):
        source = noisy(21, 13)
        frozen = source.copy()
        for algorithm in ALGORITHMS:
            result = algorithm.apply(source)
            np.testing.assert_array_equal(source, frozen, algorithm.name)
            self.assertEqual(result.shape, (13, 21, 3), algorithm.name)
            self.assertEqual(result.dtype, np.uint8, algorithm.name)
            np.testing.assert_array_equal(result, algorithm.apply(source),
                                          algorithm.name)

    def test_one_pixel_axes(self):
        for shape in [(1, 1, 3), (1, 7, 3), (7, 1, 3)]:
            source = noisy(shape[1], shape[0])
            for algorithm in ALGORITHMS:
                self.assertEqual(algorithm.apply(source).shape, shape,
                                 algorithm.name)

    def test_seam_is_reduced_on_the_worst_case(self):
        source = gradient(32, 24)
        before = seamJump(source)
        for algorithm in ALGORITHMS:
            after = seamJump(algorithm.apply(source))
            self.assertLess(after, before / 4.0,
                            f"{algorithm.name}: seam {after} vs {before}")

    def test_mirror_edges_are_exactly_equal(self):
        result = algorithmByName('Mirror fold').apply(noisy(20, 16))
        np.testing.assert_array_equal(result[:, 0], result[:, -1])
        np.testing.assert_array_equal(result[0], result[-1])

    def test_unique_names_and_lookup(self):
        names = [a.name for a in ALGORITHMS]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertIs(algorithmByName(name), ALGORITHMS[names.index(name)])
        with self.assertRaises(KeyError):
            algorithmByName('nope')


if __name__ == '__main__':
    unittest.main()
