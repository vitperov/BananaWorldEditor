# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Pre-filters: corrections applied to a texture before the seamless
# algorithm. Same image format and contract as SeamlessAlgorithms
# ((height, width, 3) uint8 array, pure function, keeps size): textures
# tile by world size (one repeat per grid square, see BoxFaces), so a
# texture must keep its square shape; the crop scales back.
#
# The user only toggles filters on or off. FILTERS is the fixed order
# the enabled ones run in, so the order is never the user's concern.
#
# Every filter has a `name` (checkbox label) and a `description`: plain
# words for a non-expert, saying which problem it fixes and what changes
# to expect. The GUI only displays it.

from typing import List, Optional, Tuple

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


def repeatScores(image: Image, axis: int) -> np.ndarray:
    """How badly the picture matches itself shifted by d pixels along
    axis, for every d in 0..length-1: mean squared channel difference
    over the overlapping part. Low = the picture repeats at distance d.
    Computed for all d at once from the autocorrelation (FFT) of every
    line along the axis plus prefix sums of squares."""
    lines = np.moveaxis(image, axis, -1).astype(np.float64)
    lines = lines.reshape(-1, lines.shape[-1])
    length = lines.shape[1]
    n = 1 << int(np.ceil(np.log2(2 * length)))
    spectrum = np.fft.rfft(lines, n=n, axis=1)
    correlation = np.fft.irfft(spectrum * np.conj(spectrum), n=n,
                               axis=1)[:, :length].sum(axis=0)
    prefix = np.concatenate([[0.0], np.cumsum((lines ** 2).sum(axis=0))])
    d = np.arange(length)
    squaredDiff = prefix[length - d] + (prefix[length] - prefix[d]) - 2.0 * correlation
    count = (length - d) * lines.shape[0]
    return np.maximum(squaredDiff, 0.0) / np.maximum(count, 1)


def localMinima(values: np.ndarray) -> np.ndarray:
    """Indices i with values[i-1] > values[i] <= values[i+1]."""
    inner = (values[1:-1] < values[:-2]) & (values[1:-1] <= values[2:])
    return np.nonzero(inner)[0] + 1


def resizePeriodic(pixels: Image, height: int, width: int) -> Image:
    """Bilinear resize of a tileable picture: pixel centres map onto
    pixel centres and the interpolation wraps around, so the pattern
    period scales exactly onto the new size and the wrap seam stays
    continuous (an edge-clamped resize would leave a step there)."""
    def axis(source, target):
        pos = (np.arange(target) + 0.5) * source / target - 0.5
        low = np.floor(pos).astype(int)
        return low % source, (low + 1) % source, (pos - low)[..., None]
    y0, y1, wy = axis(pixels.shape[0], height)
    x0, x1, wx = axis(pixels.shape[1], width)
    rows = pixels.astype(np.float32)
    rows = rows[:, x0] * (1 - wx) + rows[:, x1] * wx
    out = rows[y0] * (1 - wy[:, None]) + rows[y1] * wy[:, None]
    return toUint8(out)


def subpixelMinimum(values: np.ndarray, index: int) -> float:
    """Position of the minimum of the parabola through the three
    samples around a local minimum at index."""
    if index < 1 or index + 1 >= len(values):
        return float(index)
    left, mid, right = values[index - 1], values[index], values[index + 1]
    denominator = left - 2.0 * mid + right
    if denominator <= 0:
        return float(index)
    return index + 0.5 * (left - right) / denominator


class PeriodCrop:
    """Crop to a whole number of pattern repeats along each axis.

    Per axis: the repeat distance (period) is read off the self-match
    curve (repeatScores), then the picture is cut to the largest whole
    multiple of it that fits, at the offset where the cut edges match
    best. Opposite edges then continue the pattern when tiled. Nothing
    is cropped when no clear repeat is found or the size is already a
    whole multiple. Never crops below half the size. The crop is then
    scaled back to the original size (textures must keep their square
    shape), so the repeats get a little wider or taller.

    Period detection only trusts shifts that leave at least
    MIN_OVERLAP of the picture to compare (short overlaps match by
    chance inside flat areas). A valley counts as the pattern's repeat
    only if it is nearly as deep as the deepest one: in a running bond
    the one-row shift is a shallow valley (bricks half off) and the
    two-row shift the deep one, and the crop must follow the deep one.
    """

    name = 'Crop to whole repeats'
    description = (
        "Use for bricks, tiles, planks or any regular pattern. Trims "
        "the picture so it holds a whole number of repeats and the "
        "pattern continues across the tile edge, then stretches it back "
        "to its size, so the bricks get a little wider or taller. "
        "Nothing changes when no repeating pattern is found.")

    MIN_LENGTH = 16          # shorter axes are left alone
    MIN_OVERLAP = 0.2        # fraction of length a trusted shift keeps
    VALLEY_DEPTH = 0.6       # a valley is below this fraction of typical
    DEEP_TOLERANCE = 0.15    # deep = within this fraction of the depth
    # Misalignment (pixels) tolerated before a repeat is cut off: 1 px,
    # or 2 px when the period is 40+ px. Below that the seam error is
    # barely visible and a crop would cost a whole repeat (2 px short of
    # six 171 px repeats would otherwise lose 171 px).
    MAX_MISALIGNMENT = 2

    def apply(self, pixels: Image) -> Image:
        height, width = pixels.shape[:2]
        cropped = self.crop(pixels)
        if cropped.shape == pixels.shape:
            return cropped
        return resizePeriodic(cropped, height, width)

    def crop(self, pixels: Image) -> Image:
        """The whole-repeats crop itself, before scaling back."""
        rows = self.cropRange(pixels, axis=0)
        cols = self.cropRange(pixels, axis=1)
        return pixels[rows[0]:rows[1], cols[0]:cols[1]]

    def cropRange(self, pixels: Image, axis: int) -> Tuple[int, int]:
        """(start, stop) to keep along axis; (0, length) = no crop."""
        length = pixels.shape[axis]
        if length < self.MIN_LENGTH:
            return 0, length
        scores = repeatScores(pixels, axis)
        period = self.findPeriod(scores, length)
        if period is None:
            return 0, length
        margin = min(self.MAX_MISALIGNMENT, max(1, int(round(0.05 * period))))
        repeats = int((length + margin) // period)
        cropLength = min(length, int(round(repeats * period)))
        if length - cropLength <= margin:
            return 0, length                       # already a whole multiple
        cropLength = self.snapToMinimum(scores, cropLength, period)
        start = self.bestOffset(pixels, axis, cropLength)
        return start, start + cropLength

    def findPeriod(self, scores: np.ndarray, length: int) -> Optional[float]:
        """Repeat distance of the pattern, or None if there is none.
        Refined to sub-pixel precision from the farthest trusted valley
        that sits on a multiple of it."""
        trusted = int(length * (1.0 - self.MIN_OVERLAP))
        curve = scores[:trusted + 1]
        typical = float(np.median(curve[2:]))
        if typical <= 1e-6:
            return None                            # flat picture
        valleys = localMinima(curve)
        valleys = valleys[(valleys >= 2) & (curve[valleys] <= self.VALLEY_DEPTH * typical)]
        if len(valleys) == 0:
            return None
        deepest = float(curve[valleys].min())
        deep = valleys[curve[valleys] <= deepest + self.DEEP_TOLERANCE * (typical - deepest)]
        period = float(deep[0])
        for position in deep[::-1]:
            multiple = int(round(position / period))
            if multiple >= 1 and abs(position / period - multiple) < 0.1:
                return subpixelMinimum(curve, position) / multiple
        return subpixelMinimum(curve, deep[0])

    SNAP_GAIN = 0.75         # snap only if the minimum is below this * predicted

    @classmethod
    def snapToMinimum(cls, scores: np.ndarray, cropLength: int, period: float) -> int:
        """Move the predicted crop length to the local minimum of the
        self-match curve within +-period/8 (real periods are not whole
        pixels), but only if that minimum is distinctly lower than the
        score at the prediction: the spare part is short and may hold
        only flat content, where the curve is noise and its minimum is
        random."""
        window = max(1, int(period / 8))
        lo = max(1, cropLength - window)
        hi = min(len(scores) - 1, cropLength + window)
        candidate = lo + int(np.argmin(scores[lo:hi + 1]))
        if scores[candidate] >= cls.SNAP_GAIN * scores[cropLength]:
            return cropLength
        return candidate

    @staticmethod
    def bestOffset(pixels: Image, axis: int, cropLength: int) -> int:
        """Start of the crop: where the strip just after the crop looks
        most like the strip at its start (it follows it when tiled).
        The strip is half the spare length; its score is a moving
        average of the per-line squared difference."""
        lines = np.moveaxis(pixels, axis, -1).astype(np.float64)
        length = lines.shape[-1]
        spare = length - cropLength
        strip = max(1, spare // 2)
        perLine = ((lines[..., cropLength:] - lines[..., :spare]) ** 2)
        perLine = perLine.reshape(-1, spare).mean(axis=0)
        prefix = np.concatenate([[0.0], np.cumsum(perLine)])
        stripScores = prefix[strip:spare + 1] - prefix[:spare - strip + 1]
        return int(np.argmin(stripScores))


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


def dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Binary dilation by a square of the given radius (small masks)."""
    out = mask.copy()
    padded = np.pad(mask, radius)
    height, width = mask.shape
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out |= padded[radius + dy:radius + dy + height, radius + dx:radius + dx + width]
    return out


class HighlightSuppress:
    """Tone down glare: flash reflections, wet shine, sun glints.

    Glare in a photo is near-white: it clips at the top of the range,
    above anything the surface itself shows (measured on the catalog:
    bright mortar peaks around 230, glare sits at 245-255). So the core
    of a spot is every pixel whose brightness is near clipping (ramp
    CORE_FROM..CORE_TO), the mask is grown a little to take the soft
    halo with it, and the spot is filled with the colour of the
    non-glare pixels around it (normalised blur with the mask cut out,
    so a spot does not brighten its own replacement).

    Relative criteria (brighter than the surroundings) were tried and
    rejected: a spot dominates its own local average, so its excess
    scored *lower* than ordinary brick-mortar edges.

    Bright surfaces are not glare: when more than MAX_FRACTION of the
    picture is near-white (a white wall), nothing is changed. Stray
    near-white pixels are not glare either; only clusters are treated.
    """

    name = 'Suppress highlights'
    description = (
        "Use when the photo has shiny near-white spots: flash "
        "reflections, wet shine or sun glints. Tiled, they would repeat "
        "as a grid of bright dots. Such spots are filled with the colour "
        "of their surroundings; the rest is untouched. Does nothing on a "
        "picture that is mostly white.")

    CORE_FROM, CORE_TO = 240.0, 250.0    # brightness ramp of the glare core
    MAX_FRACTION = 0.05                  # more near-white than this: a bright surface
    MASS_SIGMA = 0.006                   # a core must be a cluster, not stray pixels
    NEAR_RADIUS = 0.05                   # neighbourhood of a core, fraction of shorter side
    SOFT_SIGMA = 0.012                   # softening before the halo test
    FILL_SIGMA = 0.06                    # background colour radius, fraction of shorter side
    HALO_FROM, HALO_TO = 15.0, 60.0      # softened brightness above background: halo ramp
    WORK_SIZE = 256                      # masks and all blurs run on a copy this big

    def apply(self, pixels: Image) -> Image:
        image = pixels.astype(np.float32)
        height, width = image.shape[:2]
        luminance = image @ np.array([0.299, 0.587, 0.114], np.float32)
        core = np.clip((luminance - self.CORE_FROM) / (self.CORE_TO - self.CORE_FROM), 0.0, 1.0)
        if not core.any() or core.mean() > self.MAX_FRACTION:
            return pixels
        small = self._Small(height, width, self.WORK_SIZE)
        shorter = min(small.height, small.width)
        # Only clusters count as glare: stray near-white pixels are part
        # of the surface (the brightest grains of mortar) and stay.
        mass = small.blur(small.down(core), max(0.5, self.MASS_SIGMA * shorter))[..., 0]
        clusters = mass > 0.35
        if not clusters.any():
            return pixels
        # Neighbourhood of the clusters (dilated, soft edge). The
        # background colour is estimated from everything outside it, so
        # neither the core nor its halo brightens its own replacement.
        near = dilate(clusters, max(2, int(round(self.NEAR_RADIUS * shorter))))
        near = small.blur(near.astype(np.float64)[..., None], 1.0)
        near = np.clip(small.up(near)[..., 0], 0.0, 1.0)
        sigma = max(1.0, self.FILL_SIGMA * shorter)
        outside = small.down(1.0 - near)
        background = small.blur(small.down(image) * outside, sigma) / np.maximum(small.blur(outside, sigma), 1e-3)
        background = small.up(background)
        backgroundLuminance = background @ np.array([0.299, 0.587, 0.114], np.float32)
        # Halo: inside the neighbourhood and still well above the
        # background. Judged on a slightly softened brightness, which
        # attenuates thin bright lines (mortar) but not a wide glow.
        softened = small.blur(small.down(luminance), max(0.5, self.SOFT_SIGMA * shorter))
        softened = small.up(softened)[..., 0]
        halo = near * np.clip((softened - backgroundLuminance - self.HALO_FROM)
                              / (self.HALO_TO - self.HALO_FROM), 0.0, 1.0)
        weight = (near * np.maximum(core, halo))[..., None]
        return toUint8(image * (1.0 - weight) + background * weight)

    class _Small:
        """Down/upscaling between full and work size (no-ops when the
        picture is already small)."""

        def __init__(self, height, width, workSize):
            scale = min(1.0, workSize / max(height, width))
            self.full = (height, width)
            self.height = max(1, round(height * scale))
            self.width = max(1, round(width * scale))
            self.same = (self.height, self.width) == self.full

        def down(self, array):
            array = array if array.ndim == 3 else array[..., None]
            if self.same:
                return array.astype(np.float64)
            return downscaleArea(array, self.height, self.width)

        def up(self, array):
            if self.same:
                return array.astype(np.float32)
            return upscaleBilinear(array.astype(np.float32), *self.full)

        @staticmethod
        def blur(array, sigma):
            return gaussianBlurReflect(array, sigma)


# Fixed execution order of the enabled filters (also the GUI order).
# Glare first: it is detected by absolute near-white brightness, which
# lighting flattening would alter (a spot inflates the local lighting
# estimate and gets darkened below the threshold), and a removed spot
# no longer skews the lighting estimate. Then geometry, then lighting.
FILTERS: List = [HighlightSuppress(), PeriodCrop(), LightingFlatten()]


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
