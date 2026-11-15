# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Turns a Box into six textured faces: positions, outward normal and
# texture coordinates per corner. No Qt dependencies: the 3D viewer and
# the exporters must agree on UVs, so both take them from here.
#
# UV rule (see PLAN-viewer.md): textures tile by world size, one repeat
# per TEXTURE_REPEAT meters, and UVs are derived from *world* position,
# not from the box's own corner. Two slabs that lie in the same plane
# therefore continue each other's texture seamlessly (a wall running
# across three squares, a wall over a window's reveal pieces), and a
# 3 m wall shows 1.5 repeats instead of one stretched copy.

from typing import List, Tuple

from modules.Geometry3D.Primitives import Box
from modules.Geometry3D.MapToPrimitives import SQUARE_SIZE

# Meters covered by one texture repeat: one grid square by default.
TEXTURE_REPEAT = SQUARE_SIZE

Vec3 = Tuple[float, float, float]
Vec2 = Tuple[float, float]

_UP: Vec3 = (0.0, 0.0, 1.0)


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def faceTangents(normal: Vec3) -> Tuple[Vec3, Vec3]:
    """World-space directions of growing u and v on a face with this normal.

    Chosen so that, looking at the face from outside, u grows to the
    right and v grows upward: tangentU x tangentV == normal, i.e. the
    texture is never mirrored, on any side of the box.

    Vertical faces: v follows world z, so a brick course stays horizontal
    and the image's bottom row sits at the floor. Horizontal faces (top
    and bottom): u follows x, v follows +y on top and -y underneath.
    """
    if normal[2] == 0:
        return _cross(_UP, normal), _UP
    if normal[2] > 0:
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)


def faceUV(point: Vec3, normal: Vec3) -> Vec2:
    """Texture coordinates of a world-space point on a face."""
    tangentU, tangentV = faceTangents(normal)
    return (_dot(point, tangentU) / TEXTURE_REPEAT,
            _dot(point, tangentV) / TEXTURE_REPEAT)


class Face:
    """One rectangular box side.

    corners: four world positions, counter-clockwise seen from outside
    (so two triangles are (0,1,2) and (0,2,3)); uvs: matching texture
    coordinates; normal: unit outward normal.
    """

    def __init__(self, normal: Vec3, corners: List[Vec3]):
        self.normal = normal
        self.corners = corners
        self.uvs = [faceUV(corner, normal) for corner in corners]

    TRIANGLE_INDICES = (0, 1, 2, 0, 2, 3)


def boxFaces(box: Box) -> List[Face]:
    """The six faces of a box, each with outward normal and world UVs."""
    x0, y0, z0 = box.origin
    x1, y1, z1 = box.maxCorner()
    return [
        Face((-1.0, 0.0, 0.0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
        Face((+1.0, 0.0, 0.0), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
        Face((0.0, -1.0, 0.0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
        Face((0.0, +1.0, 0.0), [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)]),
        Face((0.0, 0.0, -1.0), [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)]),
        Face((0.0, 0.0, +1.0), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
    ]
