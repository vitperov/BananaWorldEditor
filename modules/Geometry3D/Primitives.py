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


# Footprint corners of a prism, in cyclic order. Heights in `bottom`
# and `top` follow this order.
#   0: (x0, y0)   1: (x1, y0)   2: (x1, y1)   3: (x0, y1)
PRISM_CORNERS = ((0, 0), (1, 0), (1, 1), (0, 1))


class Prism(Box):
    """Vertical prism over the box footprint with a height per corner.

    `bottom` and `top` give, for each footprint corner (PRISM_CORNERS
    order), the z of the bottom and top surface in meters above the
    origin, with 0 <= bottom[i] <= top[i] <= size z. All of box, roof
    wedge, hip/valley corner and sloped constant-thickness slab are
    spellings of this one shape:
        bottom (0,0,0,0) top (3,3,3,3)          box
        bottom (0,0,0,0) top (0,0,3,3)          wedge rising toward +y
        bottom (0,0,0,0) top (0,0,3,0)          hip, high corner (x1,y1)
        bottom (0,0,1,1) top (0.1,0.1,1.1,1.1)  sloped roof slab

    A non-planar bottom/top quad is split into two triangles along a
    diagonal ('02' or '13'). By default the crease bulges outward
    (ridges and hips); set topCrease/bottomCrease to force the other
    diagonal for concave surfaces (roof valleys).
    """

    CREASES = ('02', '13')

    def __init__(self, origin, size,
                 bottom, top,
                 topCrease: Optional[str] = None,
                 bottomCrease: Optional[str] = None,
                 textureSlot: Optional[str] = None,
                 texture: Optional[str] = None):
        super().__init__(origin, size, textureSlot, texture)
        self.bottom = tuple(float(h) for h in bottom)
        self.top = tuple(float(h) for h in top)
        if len(self.bottom) != 4 or len(self.top) != 4:
            raise ValueError("Prism needs 4 bottom and 4 top heights")
        for b, t in zip(self.bottom, self.top):
            if not (-EPSILON <= b <= t <= self.size[2] + EPSILON):
                raise ValueError(
                    f"Prism heights must satisfy 0 <= bottom <= top <= "
                    f"{self.size[2]}: {self.bottom} {self.top}")
        for crease in (topCrease, bottomCrease):
            if crease is not None and crease not in self.CREASES:
                raise ValueError(f"Bad crease: {crease!r}")
        self.topCrease = topCrease
        self.bottomCrease = bottomCrease

    @staticmethod
    def _crease(heights, explicit: Optional[str],
                outwardUp: bool) -> Optional[str]:
        """Diagonal to split along, or None for a planar quad."""
        defect = heights[0] + heights[2] - heights[1] - heights[3]
        if abs(defect) <= EPSILON:
            return None
        if explicit is not None:
            return explicit
        # Default: the crease line bulges toward the outside of the
        # solid (up for the top surface, down for the bottom).
        bulgesUp = defect > 0
        return '02' if bulgesUp == outwardUp else '13'

    def resolvedTopCrease(self) -> Optional[str]:
        return self._crease(self.top, self.topCrease, True)

    def resolvedBottomCrease(self) -> Optional[str]:
        return self._crease(self.bottom, self.bottomCrease, False)

    @staticmethod
    def _surfaceVolume(heights, crease) -> float:
        """Mean height over the unit footprint of one surface."""
        if crease is None:
            return sum(heights) / 4.0
        i = 0 if crease == '02' else 1
        tri1 = (heights[i], heights[(i + 1) % 4], heights[(i + 2) % 4])
        tri2 = (heights[i], heights[(i + 2) % 4], heights[(i + 3) % 4])
        return (sum(tri1) + sum(tri2)) / 6.0

    def volume(self) -> float:
        area = self.size[0] * self.size[1]
        return area * (self._surfaceVolume(self.top, self.resolvedTopCrease())
                       - self._surfaceVolume(self.bottom,
                                             self.resolvedBottomCrease()))

    @staticmethod
    def _rotatedCrease(crease: Optional[str]) -> Optional[str]:
        if crease is None:
            return None
        return '13' if crease == '02' else '02'

    def translated(self, offset) -> 'Prism':
        box = super().translated(offset)
        return Prism(box.origin, box.size, self.bottom, self.top,
                     self.topCrease, self.bottomCrease,
                     self.textureSlot, self.texture)

    def rotated90(self, cx: float, cy: float) -> 'Prism':
        # Footprint corner i moves to corner position (i + 1) % 4.
        box = super().rotated90(cx, cy)
        shift = lambda h: (h[3], h[0], h[1], h[2])
        return Prism(box.origin, box.size, shift(self.bottom), shift(self.top),
                     self._rotatedCrease(self.topCrease),
                     self._rotatedCrease(self.bottomCrease),
                     self.textureSlot, self.texture)

    def approxEquals(self, other: 'Box', eps: float = EPSILON) -> bool:
        return (isinstance(other, Prism)
                and all(abs(a - b) <= eps
                        for a, b in zip(self.bottom + self.top,
                                        other.bottom + other.top))
                and self.resolvedTopCrease() == other.resolvedTopCrease()
                and self.resolvedBottomCrease() == other.resolvedBottomCrease()
                and super().approxEquals(other, eps))

    def __repr__(self):
        return (f"Prism(origin={self.origin}, size={self.size}, "
                f"bottom={self.bottom}, top={self.top}, "
                f"textureSlot={self.textureSlot!r}, texture={self.texture!r})")
