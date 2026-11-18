# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Denoise: grain inside flat areas is reduced, edges keep their
# contrast, and a clean picture is left alone.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.PreFilters import Denoise, noiseSigma
from test_period_crop import BRICK, MORTAR, PX, PY


def cleanWall(width=200, height=150):
    """Brick pattern without any noise."""
    y, x = np.mgrid[0:height, 0:width]
    brick = ((x + 11) % PX < PX - 4) & ((y + 5) % PY < PY - 3)
    return np.where(brick[..., None], BRICK, MORTAR).astype(np.uint8)


def addNoise(image, sigma, seed=0):
    rng = np.random.default_rng(seed)
    noisy = image.astype(float) + rng.normal(0, sigma, image.shape)
    return np.clip(noisy, 0, 255).astype(np.uint8)


def interior(width=200, height=150, margin=3):
    """Pixels at least `margin` px away from any brick/mortar edge."""
    y, x = np.mgrid[0:height, 0:width]
    bx, by = (x + 11) % PX, (y + 5) % PY
    return ((bx >= margin) & (bx < PX - 4 - margin)
            & (by >= margin) & (by < PY - 3 - margin))


class DenoiseTest(unittest.TestCase):

    def test_noise_sigma_estimate(self):
        weights = np.array([0.299, 0.587, 0.114])
        noisy = addNoise(cleanWall(), 12).astype(float) @ weights
        # Independent channel noise adds in quadrature in the luminance.
        expected = 12 * np.sqrt((weights ** 2).sum())
        self.assertAlmostEqual(noiseSigma(noisy), expected, delta=1.0)

    def test_grain_reduced_in_flat_areas(self):
        clean, noisy = cleanWall(), addNoise(cleanWall(), 12)
        out = Denoise().apply(noisy)
        flat = interior()
        before = np.abs(noisy.astype(float) - clean)[flat].mean()
        after = np.abs(out.astype(float) - clean)[flat].mean()
        self.assertLess(after, before / 2.5)

    def test_edges_keep_contrast(self):
        noisy = addNoise(cleanWall(), 12)
        out = Denoise().apply(noisy).astype(float)
        # Mortar column at x = 26..29: the step from brick (x=25) to
        # mortar (x=27) keeps most of its height.
        step = np.abs(out[:, 27] - out[:, 24]).mean()
        cleanStep = np.abs(cleanWall()[:, 27].astype(float) - cleanWall()[:, 24]).mean()
        self.assertGreater(step, 0.8 * cleanStep)

    def test_clean_picture_untouched(self):
        clean = cleanWall()
        np.testing.assert_array_equal(Denoise().apply(clean), clean)

    def test_lightly_noisy_picture_barely_changed(self):
        light = addNoise(cleanWall(), 2)
        out = Denoise().apply(light)
        self.assertLess(np.abs(out.astype(int) - light).mean(), 2.0)


if __name__ == '__main__':
    unittest.main()
