# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Pre-filters: corrections applied to a texture before the seamless
# algorithm. Same grid format and contract as SeamlessAlgorithms (pure
# function, keeps size, 0..255 values); numpy does the work inside.
#
# The user only toggles filters on or off. FILTERS is the fixed order
# the enabled ones run in, so the order is never the user's concern.

from typing import List

import numpy as np

from modules.TextureEditor.SeamlessAlgorithms import Grid


def gridToArray(grid: Grid) -> np.ndarray:
    return np.asarray(grid, dtype=np.float64).reshape(len(grid), len(grid[0]), 3)


def arrayToGrid(array: np.ndarray) -> Grid:
    array = np.clip(np.rint(array), 0, 255).astype(np.uint8)
    return [[tuple(int(c) for c in pixel) for pixel in row] for row in array]


def gaussianBlurReflect(array: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur of an H x W x C array with mirrored borders.

    Mirroring (not wrapping) matters: the input is usually not tileable
    yet, and a wrapped blur would mix the left edge into the right one,
    biasing the result exactly where the seam is. The mirrored 2H x 2W
    image is periodic, so the blur is one exact FFT multiply."""
    height, width = array.shape[:2]
    mirrored = np.concatenate([array, array[::-1]], axis=0)
    mirrored = np.concatenate([mirrored, mirrored[:, ::-1]], axis=1)
    fy = np.fft.fftfreq(2 * height)[:, None]
    fx = np.fft.rfftfreq(2 * width)[None, :]
    kernel = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    spectrum = np.fft.rfft2(mirrored, axes=(0, 1)) * kernel[..., None]
    blurred = np.fft.irfft2(spectrum, s=(2 * height, 2 * width), axes=(0, 1))
    return blurred[:height, :width]


def quadraticSurface(array: np.ndarray) -> np.ndarray:
    """Least-squares fit of a*1 + b*x + c*y + d*x^2 + e*xy + f*y^2 per
    channel. Captures linear gradients and vignettes exactly, with no
    border bias (a blur alone underestimates a slope at the edges)."""
    height, width = array.shape[:2]
    v, u = np.mgrid[-1:1:height * 1j, -1:1:width * 1j]
    basis = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v],
                     axis=-1).reshape(-1, 6)
    coeffs, *_ = np.linalg.lstsq(basis, array.reshape(-1, 3), rcond=None)
    return (basis @ coeffs).reshape(height, width, 3)


class LightingFlatten:
    """Remove uneven lighting: gradients, vignetting, soft shadows.

    Two stages, both divided out (light multiplies surface color, so a
    shadowed area keeps its texture contrast instead of going flat):
      1. a quadratic surface fit removes gradients and vignettes;
      2. a heavy blur of what is left removes broad irregular shadows.
    Each channel is then scaled back to its original mean.

    The blur sigma is fixed at 1/8 of the shorter side, relative so it
    behaves the same at any resolution. Measured on synthetic textures:
    gradients and vignettes ~97% removed; features repeating 4+ times per
    tile keep full contrast, 2 times keep ~85%. A smaller sigma removes
    more shadow but starts eating 2-repeat features. A texture whose one
    real feature spans the whole image cannot be told from light."""

    name = 'Flatten lighting'
    SIGMA_FRACTION = 1.0 / 8.0
    EPSILON = 1.0

    def apply(self, grid: Grid) -> Grid:
        image = gridToArray(grid)
        flat = image / np.maximum(quadraticSurface(image), self.EPSILON)
        sigma = self.SIGMA_FRACTION * min(image.shape[:2])
        flat = flat / np.maximum(gaussianBlurReflect(flat, sigma), 1e-3)
        scale = image.mean(axis=(0, 1)) / np.maximum(flat.mean(axis=(0, 1)), 1e-9)
        return arrayToGrid(flat * scale)


# Fixed execution order of the enabled filters (also the GUI order).
FILTERS: List = [LightingFlatten()]


def filterByName(name: str):
    for prefilter in FILTERS:
        if prefilter.name == name:
            return prefilter
    raise KeyError(f"Unknown pre-filter: {name}")


def applyFilters(grid: Grid, enabledNames) -> Grid:
    for prefilter in FILTERS:
        if prefilter.name in enabledNames:
            grid = prefilter.apply(grid)
    return grid
