# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Pre-filters: corrections applied to a texture before the seamless
# algorithm. Same image format and contract as SeamlessAlgorithms
# ((height, width, 3) uint8 array, pure function, keeps size).
#
# The user only toggles filters on or off. FILTERS is the fixed order
# the enabled ones run in, so the order is never the user's concern.
#
# Every filter has a `name` (checkbox label) and a `description`: plain
# words for a non-expert, saying which problem it fixes and what changes
# to expect. The GUI only displays it.

from typing import List

import numpy as np

from modules.TextureEditor.SeamlessAlgorithms import Image


def toUint8(array: np.ndarray) -> Image:
    """Round and clip a float array to uint8 (works in place on it)."""
    array = np.rint(array, out=array)
    return np.clip(array, 0, 255, out=array).astype(np.uint8)


# Lighting is smooth, so it is estimated on a copy whose longer side is
# at most this many pixels and scaled back up: same result, a fraction
# of the time on 1024+ textures.
LIGHTING_WORK_SIZE = 256


def downscaleArea(array: np.ndarray, height: int, width: int) -> np.ndarray:
    """Average of the source pixels falling into each target pixel.
    uint8 input is summed in uint32: no full-size float copy."""
    srcH, srcW = array.shape[:2]
    if srcH % height == 0 and srcW % width == 0:     # e.g. 1024 -> 256
        # Add whole row slices, then column slices: a few contiguous
        # adds, ~15x faster than a block sum over strided axes.
        fy, fx = srcH // height, srcW // width
        channels = array.shape[2]
        rows = array.reshape(height, fy, srcW * channels)
        acc = rows[:, 0].astype(np.uint32 if array.dtype == np.uint8 else np.float64)
        for i in range(1, fy):
            acc += rows[:, i]
        cols = acc.reshape(height, width, fx, channels)
        out = cols[:, :, 0].copy()
        for i in range(1, fx):
            out += cols[:, :, i]
        return out / float(fy * fx)
    rows = (np.arange(height) * array.shape[0]) // height
    cols = (np.arange(width) * array.shape[1]) // width
    sumType = np.uint32 if array.dtype == np.uint8 else np.float64
    sums = np.add.reduceat(array, rows, axis=0, dtype=sumType)
    sums = np.add.reduceat(sums, cols, axis=1, dtype=sumType)
    rowCounts = np.diff(np.append(rows, array.shape[0]))
    colCounts = np.diff(np.append(cols, array.shape[1]))
    return sums / (rowCounts[:, None, None] * colCounts[None, :, None])


def upscaleBilinear(array: np.ndarray, height: int, width: int) -> np.ndarray:
    """Pixel-center-aligned bilinear upscale, in the array's dtype.
    Horizontal pass first, on the few source rows; the vertical pass
    then only copies and blends whole rows (no column gathers at full
    size)."""
    def axisWeights(source, target):
        pos = np.clip((np.arange(target) + 0.5) * source / target - 0.5,
                      0, source - 1)
        low = np.floor(pos).astype(int)
        high = np.minimum(low + 1, source - 1)
        return low, high, (pos - low).astype(array.dtype)
    y0, y1, wy = axisWeights(array.shape[0], height)
    x0, x1, wx = axisWeights(array.shape[1], width)
    across = (array[:, x0] * (1 - wx)[None, :, None] +
              array[:, x1] * wx[None, :, None])
    out = across[y0]
    out *= (1 - wy)[:, None, None]
    out += across[y1] * wy[:, None, None]
    return out


def channelMean(array: np.ndarray) -> np.ndarray:
    """Per-channel mean of an H x W x C array. Summing rows first is ~6x
    faster than mean(axis=(0, 1)) on interleaved channels."""
    rows = array.sum(axis=0, dtype=np.float64)
    return rows.sum(axis=0) / (array.shape[0] * array.shape[1])


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
    description = (
        "Use when the photo is lighter on one side or darker in the "
        "corners: tiled, it shows as a repeating light-dark pattern. "
        "Keeps bricks, planks and cracks; may fade one huge feature "
        "that fills half the picture.")
    SIGMA_FRACTION = 1.0 / 8.0
    EPSILON = 1.0

    def apply(self, pixels: Image) -> Image:
        height, width = pixels.shape[:2]
        scale = min(1.0, LIGHTING_WORK_SIZE / max(height, width))
        if scale < 1.0:
            small = downscaleArea(pixels, max(1, round(height * scale)),
                                  max(1, round(width * scale)))
        else:
            small = pixels.astype(np.float64)
        # Full-size work is one multiply by the inverse lighting, in
        # float32: plenty for 0..255 values, half the memory traffic.
        inverse = (1.0 / self._lighting(small)).astype(np.float32)
        if scale < 1.0:
            inverse = upscaleBilinear(inverse, height, width)
        flat = pixels.astype(np.float32)
        flat *= inverse
        gain = channelMean(pixels) / np.maximum(channelMean(flat), 1e-9)
        flat *= gain.astype(np.float32)
        return toUint8(flat)

    def _lighting(self, image: np.ndarray) -> np.ndarray:
        """Brightness map to divide out: quadratic fit times the heavy
        blur of what the fit leaves."""
        surface = np.maximum(quadraticSurface(image), self.EPSILON)
        residual = image / surface
        sigma = self.SIGMA_FRACTION * min(image.shape[:2])
        return surface * np.maximum(gaussianBlurReflect(residual, sigma), 1e-3)


# Fixed execution order of the enabled filters (also the GUI order).
FILTERS: List = [LightingFlatten()]


def filterByName(name: str):
    for prefilter in FILTERS:
        if prefilter.name == name:
            return prefilter
    raise KeyError(f"Unknown pre-filter: {name}")


def applyFilters(pixels: Image, enabledNames) -> Image:
    for prefilter in FILTERS:
        if prefilter.name in enabledNames:
            pixels = prefilter.apply(pixels)
    return pixels
