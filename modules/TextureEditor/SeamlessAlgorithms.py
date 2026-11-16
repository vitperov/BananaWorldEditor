# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Algorithms that turn a texture into a seamlessly tileable one.
# No Qt dependencies: an image is a list of rows, a row is a list of
# (r, g, b) tuples with 0..255 ints. The texture editor window converts
# QImage to this grid and back; the unit tests use the grids directly.
#
# Every algorithm is a pure function of the input grid and keeps the
# image size. "Original" (no conversion) is represented by the absence
# of an algorithm, not by a class here.

from typing import List, Tuple

Pixel = Tuple[int, int, int]
Grid = List[List[Pixel]]


def _lerp(a: Pixel, b: Pixel, t: float) -> Pixel:
    return tuple(int(round(ca + (cb - ca) * t)) for ca, cb in zip(a, b))


def _smoothstep(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


class MirrorFold:
    """Mirror the far half of the image back onto itself, on both axes.

    The right/bottom halves become reflections of the left/top halves,
    so opposite edges are identical and the tile repeats without a
    jump. Cheap and lossless near the edges, but the content becomes
    symmetric and the mirror line may show on structured textures.
    """

    name = 'Mirror fold'

    def apply(self, pixels: Grid) -> Grid:
        height, width = len(pixels), len(pixels[0])

        def fold(i, n):
            return i if i < (n + 1) // 2 else n - 1 - i

        return [[pixels[fold(y, height)][fold(x, width)]
                 for x in range(width)] for y in range(height)]


class OffsetBlend:
    """GIMP-style "make seamless": blend with a half-offset copy.

    The image is wrapped by half its size (which moves the old edges to
    the center and makes the new edges continuous by construction), and
    the two layers are cross-faded: original in the center, offset copy
    toward the borders. Content is preserved, but overlapping doubles
    features in the blend band (ghosting) on high-contrast textures.
    """

    name = 'Offset blend'

    def apply(self, pixels: Grid) -> Grid:
        height, width = len(pixels), len(pixels[0])
        shiftX, shiftY = width // 2, height // 2
        out = []
        for y in range(height):
            row = []
            dy = abs(y - (height - 1) / 2.0) / ((height - 1) / 2.0)
            for x in range(width):
                dx = abs(x - (width - 1) / 2.0) / ((width - 1) / 2.0)
                # 0 in the center half of each axis, 1 at the border.
                alpha = _smoothstep(max(dx, dy) * 2.0 - 1.0)
                shifted = pixels[(y + shiftY) % height][(x + shiftX) % width]
                row.append(_lerp(pixels[y][x], shifted, alpha))
            out.append(row)
        return out


class OverlapCrossfade:
    """Photoshop-style overlap: wrap a margin strip over the far edge.

    A quarter-size strip from the right/bottom is laid over the
    left/top edge with a linear cross-fade (the standard overlap trick
    used when hand-making tiles), then the slightly smaller result is
    scaled back to the original size bilinearly. No mirroring and no
    center ghosting; the whole image grows by a few percent.
    """

    name = 'Overlap crossfade'

    def apply(self, pixels: Grid) -> Grid:
        height, width = len(pixels), len(pixels[0])
        blended = self._foldAxis(pixels, width)                 # columns
        transposed = [list(row) for row in zip(*blended)]
        blended = self._foldAxis(transposed, height)            # rows
        result = [list(row) for row in zip(*blended)]
        return self._resize(result, width, height)

    @staticmethod
    def _foldAxis(pixels: Grid, length: int) -> Grid:
        margin = max(1, length // 4)
        kept = length - margin
        out = []
        for row in pixels:
            newRow = []
            for x in range(kept):
                if x < margin:
                    alpha = (x + 1) / (margin + 1)
                    newRow.append(_lerp(row[kept + x], row[x], alpha))
                else:
                    newRow.append(row[x])
            out.append(newRow)
        return out

    @staticmethod
    def _resize(pixels: Grid, width: int, height: int) -> Grid:
        srcH, srcW = len(pixels), len(pixels[0])
        out = []
        for y in range(height):
            fy = y * (srcH - 1) / (height - 1) if height > 1 else 0.0
            y0 = min(int(fy), srcH - 2) if srcH > 1 else 0
            ty = fy - y0
            row = []
            for x in range(width):
                fx = x * (srcW - 1) / (width - 1) if width > 1 else 0.0
                x0 = min(int(fx), srcW - 2) if srcW > 1 else 0
                tx = fx - x0
                top = _lerp(pixels[y0][x0], pixels[y0][min(x0 + 1, srcW - 1)], tx)
                bottom = _lerp(pixels[min(y0 + 1, srcH - 1)][x0],
                               pixels[min(y0 + 1, srcH - 1)][min(x0 + 1, srcW - 1)], tx)
                row.append(_lerp(top, bottom, ty))
            out.append(row)
        return out


# Dropdown order in the texture editor.
ALGORITHMS = [MirrorFold(), OffsetBlend(), OverlapCrossfade()]


def algorithmByName(name: str):
    for algorithm in ALGORITHMS:
        if algorithm.name == name:
            return algorithm
    raise KeyError(f"Unknown seamless algorithm: {name}")
