# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Algorithms that turn a texture into a seamlessly tileable one.
# No Qt dependencies: an image is a numpy uint8 array of shape
# (height, width, 3), RGB. The texture editor window converts QImage to
# this array and back; the unit tests use the arrays directly.
#
# Every algorithm is a pure function of the input image (never modifies
# it) and keeps the image size. All work is vectorized numpy. "Original"
# (no conversion) is represented by the absence of an algorithm, not by
# a class here.

import numpy as np

Image = np.ndarray      # (height, width, 3) uint8, RGB


def _lerp(a: np.ndarray, b: np.ndarray, t) -> np.ndarray:
    """a..b at t, rounded half-to-even to uint8; t broadcasts against
    the pixel arrays (scalar, per row or per column)."""
    a = a.astype(np.float64)
    return np.rint(a + (b.astype(np.float64) - a) * t).astype(np.uint8)


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class MirrorFold:
    """Mirror the far half of the image back onto itself, on both axes.

    The right/bottom halves become reflections of the left/top halves,
    so opposite edges are identical and the tile repeats without a
    jump. Cheap and lossless near the edges, but the content becomes
    symmetric and the mirror line may show on structured textures.
    """

    name = 'Mirror fold'

    def apply(self, pixels: Image) -> Image:
        height, width = pixels.shape[:2]

        def fold(n):
            i = np.arange(n)
            return np.where(i < (n + 1) // 2, i, n - 1 - i)

        return pixels[fold(height)][:, fold(width)]


class OffsetBlend:
    """GIMP-style "make seamless": blend with a half-offset copy.

    The image is wrapped by half its size (which moves the old edges to
    the center and makes the new edges continuous by construction), and
    the two layers are cross-faded: original in the center, offset copy
    toward the borders. Content is preserved, but overlapping doubles
    features in the blend band (ghosting) on high-contrast textures.
    """

    name = 'Offset blend'

    def apply(self, pixels: Image) -> Image:
        height, width = pixels.shape[:2]
        shifted = np.roll(pixels, (-(height // 2), -(width // 2)), axis=(0, 1))

        def distance(n):
            # 0 at the center, 1 at both borders (a 1-pixel axis is
            # all center).
            if n == 1:
                return np.zeros(1)
            half = (n - 1) / 2.0
            return np.abs(np.arange(n) - half) / half

        # 0 in the center half of each axis, 1 at the border.
        alpha = _smoothstep(np.maximum(distance(height)[:, None],
                                       distance(width)[None, :]) * 2.0 - 1.0)
        return _lerp(pixels, shifted, alpha[..., None])


class OverlapCrossfade:
    """Photoshop-style overlap: wrap a margin strip over the far edge.

    A quarter-size strip from the right/bottom is laid over the
    left/top edge with a linear cross-fade (the standard overlap trick
    used when hand-making tiles), then the slightly smaller result is
    scaled back to the original size bilinearly. No mirroring and no
    center ghosting; the whole image grows by a few percent.
    """

    name = 'Overlap crossfade'

    def apply(self, pixels: Image) -> Image:
        height, width = pixels.shape[:2]
        blended = self._foldAxis(pixels, axis=1)                # columns
        blended = self._foldAxis(blended, axis=0)               # rows
        return self._resize(blended, width, height)

    @staticmethod
    def _foldAxis(pixels: Image, axis: int) -> Image:
        """Keep the first length - margin lines; fade the last margin
        lines in over the first ones."""
        view = np.moveaxis(pixels, axis, 1)
        length = view.shape[1]
        if length < 2:          # a single line already tiles
            return pixels
        margin = max(1, length // 4)
        kept = length - margin
        out = view[:, :kept].copy()
        alpha = (np.arange(margin) + 1) / (margin + 1)
        out[:, :margin] = _lerp(view[:, kept:kept + margin], view[:, :margin],
                                alpha[None, :, None])
        return np.moveaxis(out, 1, axis)

    @staticmethod
    def _resize(pixels: Image, width: int, height: int) -> Image:
        """Corner-aligned bilinear resize, rounded after the horizontal
        pass (done once over the source rows) and after the vertical."""
        srcH, srcW = pixels.shape[:2]

        def axis(target, source):
            if target > 1:
                pos = np.arange(target) * (source - 1) / (target - 1)
            else:
                pos = np.zeros(target)
            low = (np.minimum(pos.astype(int), source - 2) if source > 1
                   else np.zeros(target, int))
            high = np.minimum(low + 1, source - 1)
            return low, high, pos - low

        y0, y1, ty = axis(height, srcH)
        x0, x1, tx = axis(width, srcW)
        across = _lerp(pixels[:, x0], pixels[:, x1], tx[None, :, None])
        return _lerp(across[y0], across[y1], ty[:, None, None])


# Dropdown order in the texture editor.
ALGORITHMS = [MirrorFold(), OffsetBlend(), OverlapCrossfade()]


def algorithmByName(name: str):
    for algorithm in ALGORITHMS:
        if algorithm.name == name:
            return algorithm
    raise KeyError(f"Unknown seamless algorithm: {name}")
