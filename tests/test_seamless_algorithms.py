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
import random
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.SeamlessAlgorithms import (ALGORITHMS,
                                                      algorithmByName)


def gradient(width, height):
    """Horizontal+vertical gradient: the least tileable image there is."""
    return [[(int(255 * x / (width - 1)), int(255 * y / (height - 1)), 128)
             for x in range(width)] for y in range(height)]


def noisy(width, height, seed=7):
    rng = random.Random(seed)
    return [[(rng.randrange(256), rng.randrange(256), rng.randrange(256))
             for _ in range(width)] for _ in range(height)]


def seamJump(pixels):
    """Mean channel difference across the tile wrap, both axes."""
    height, width = len(pixels), len(pixels[0])
    total, count = 0, 0
    for y in range(height):
        for a, b in zip(pixels[y][0], pixels[y][width - 1]):
            total += abs(a - b)
            count += 1
    for x in range(width):
        for a, b in zip(pixels[0][x], pixels[height - 1][x]):
            total += abs(a - b)
            count += 1
    return total / count


class SeamlessAlgorithms(unittest.TestCase):

    def test_size_range_and_purity(self):
        source = noisy(21, 13)
        frozen = [row[:] for row in source]
        for algorithm in ALGORITHMS:
            result = algorithm.apply(source)
            self.assertEqual(source, frozen, algorithm.name)  # input untouched
            self.assertEqual((len(result), len(result[0])), (13, 21),
                             algorithm.name)
            for row in result:
                for pixel in row:
                    self.assertEqual(len(pixel), 3)
                    for channel in pixel:
                        self.assertTrue(0 <= channel <= 255, algorithm.name)
            self.assertEqual(result, algorithm.apply(source), algorithm.name)

    def test_seam_is_reduced_on_the_worst_case(self):
        source = gradient(32, 24)
        before = seamJump(source)
        for algorithm in ALGORITHMS:
            after = seamJump(algorithm.apply(source))
            self.assertLess(after, before / 4.0,
                            f"{algorithm.name}: seam {after} vs {before}")

    def test_mirror_edges_are_exactly_equal(self):
        result = algorithmByName('Mirror fold').apply(noisy(20, 16))
        for row in result:
            self.assertEqual(row[0], row[-1])
        self.assertEqual(result[0], result[-1])

    def test_unique_names_and_lookup(self):
        names = [a.name for a in ALGORITHMS]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertIs(algorithmByName(name), ALGORITHMS[names.index(name)])
        with self.assertRaises(KeyError):
            algorithmByName('nope')


if __name__ == '__main__':
    unittest.main()
