# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Pure-Python 3D primitives for generated object geometry.
# No Qt dependencies: this module is shared by the 3D viewer, the
# exporters and the unit tests.

from typing import List, Optional, Tuple

# Overlap/bounds comparisons tolerance. Box edges that merely touch
# (shared face) must not count as intersecting.
EPSILON = 1e-9


class Box:
    """Axis-aligned box: origin is the min corner, size is positive extents.

    Coordinates are in meters, in map orientation: x/y span the ground
    plane exactly as the 2D editor draws them, z points up.
    """

    def __init__(self, origin: Tuple[float, float, float],
                 size: Tuple[float, float, float],
                 textureSlot: Optional[str] = None,
                 texture: Optional[str] = None):
        self.origin = (float(origin[0]), float(origin[1]), float(origin[2]))
        self.size = (float(size[0]), float(size[1]), float(size[2]))
        self.textureSlot = textureSlot
        self.texture = texture

    def maxCorner(self) -> Tuple[float, float, float]:
        return (self.origin[0] + self.size[0],
                self.origin[1] + self.size[1],
                self.origin[2] + self.size[2])

    def volume(self) -> float:
        return self.size[0] * self.size[1] * self.size[2]

    def translated(self, offset: Tuple[float, float, float]) -> 'Box':
        return Box((self.origin[0] + offset[0],
                    self.origin[1] + offset[1],
                    self.origin[2] + offset[2]),
                   self.size, self.textureSlot, self.texture)

    def rotated90(self, cx: float, cy: float) -> 'Box':
        """Rotate 90 degrees around the vertical axis through (cx, cy).

        Rotation direction matches the 2D editor, which draws y downward
        on screen and rotates icons with QTransform().rotate() (clockwise
        on screen). In map coordinates that is (dx, dy) -> (-dy, dx).
        90-degree steps keep the box axis-aligned, so the result is again
        a min-corner/size pair.
        """
        x0, y0, z0 = self.origin
        x1, y1, _ = self.maxCorner()
        newOrigin = (cx - (y1 - cy), cy + (x0 - cx), z0)
        newSize = (self.size[1], self.size[0], self.size[2])
        return Box(newOrigin, newSize, self.textureSlot, self.texture)

    def intersects(self, other: 'Box') -> bool:
        """True when interiors overlap. Touching faces do not count."""
        aMax = self.maxCorner()
        bMax = other.maxCorner()
        for axis in range(3):
            if self.origin[axis] >= bMax[axis] - EPSILON:
                return False
            if other.origin[axis] >= aMax[axis] - EPSILON:
                return False
        return True

    def approxEquals(self, other: 'Box', eps: float = EPSILON) -> bool:
        return (all(abs(a - b) <= eps for a, b in zip(self.origin, other.origin))
                and all(abs(a - b) <= eps for a, b in zip(self.size, other.size))
                and self.textureSlot == other.textureSlot)

    def __repr__(self):
        return (f"Box(origin={self.origin}, size={self.size}, "
                f"textureSlot={self.textureSlot!r}, texture={self.texture!r})")
