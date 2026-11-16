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

from modules.Geometry3D.Primitives import Box, Prism, PRISM_CORNERS
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


def _normalized(v: Vec3) -> Vec3:
    length = (v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) ** 0.5
    return (v[0] / length, v[1] / length, v[2] / length)


def faceTangents(normal: Vec3) -> Tuple[Vec3, Vec3]:
    """World-space directions of growing u and v on a face with this normal.

    Chosen so that, looking at the face from outside, u grows to the
    right and v grows upward: tangentU x tangentV == normal, i.e. the
    texture is never mirrored, on any side of the box.

    Vertical faces: v follows world z, so a brick course stays horizontal
    and the image's bottom row sits at the floor. Horizontal faces (top
    and bottom): u follows x, v follows +y on top and -y underneath.
    Sloped faces (roofs): u stays horizontal along the eave, v runs up
    the slope, so tile courses stay level and continue across squares.
    """
    if normal[2] == 0:
        return _cross(_UP, normal), _UP
    if abs(normal[2]) >= 1.0 - 1e-12:
        if normal[2] > 0:
            return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        return (1.0, 0.0, 0.0), (0.0, -1.0, 0.0)
    tangentU = _normalized(_cross(_UP, normal))
    return tangentU, _cross(normal, tangentU)


def faceUV(point: Vec3, normal: Vec3) -> Vec2:
    """Texture coordinates of a world-space point on a face."""
    tangentU, tangentV = faceTangents(normal)
    return (_dot(point, tangentU) / TEXTURE_REPEAT,
            _dot(point, tangentV) / TEXTURE_REPEAT)


class Face:
    """One flat side of a primitive: a triangle or a convex quad.

    corners: world positions, counter-clockwise seen from outside;
    uvs: matching texture coordinates; normal: unit outward normal;
    triangleIndices: fan triangulation of the corners.
    """

    def __init__(self, normal: Vec3, corners: List[Vec3]):
        self.normal = normal
        self.corners = corners
        self.uvs = [faceUV(corner, normal) for corner in corners]
        self.triangleIndices = ((0, 1, 2) if len(corners) == 3
                                else self.TRIANGLE_INDICES)

    TRIANGLE_INDICES = (0, 1, 2, 0, 2, 3)


def _orientedFace(corners: List[Vec3], outwardHint: Vec3) -> Face:
    """Face from a flat polygon: the unit normal comes from the polygon
    itself, the winding is reversed if needed so the normal points to
    the same side as outwardHint."""
    normal = (0.0, 0.0, 0.0)
    for i in range(len(corners)):
        a, b = corners[i], corners[(i + 1) % len(corners)]
        normal = (normal[0] + (a[1] - b[1]) * (a[2] + b[2]),
                  normal[1] + (a[2] - b[2]) * (a[0] + b[0]),
                  normal[2] + (a[0] - b[0]) * (a[1] + b[1]))
    if _dot(normal, outwardHint) < 0:
        corners = list(reversed(corners))
        normal = (-normal[0], -normal[1], -normal[2])
    return Face(_normalized(normal), corners)


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


def prismFaces(prism: Prism) -> List[Face]:
    """Faces of a prism: bottom and top surfaces (each one quad, or two
    triangles along the resolved crease), plus a vertical face per
    footprint side. Sides where bottom meets top degenerate into a
    triangle or vanish (a roof wedge's eave edge)."""
    x0, y0, z0 = prism.origin
    x1, y1 = x0 + prism.size[0], y0 + prism.size[1]
    xs, ys = (x0, x1), (y0, y1)
    corners = [(xs[cx], ys[cy]) for cx, cy in PRISM_CORNERS]
    bottom = [(x, y, z0 + h) for (x, y), h in zip(corners, prism.bottom)]
    top = [(x, y, z0 + h) for (x, y), h in zip(corners, prism.top)]

    faces = []

    def horizontal(points, crease, hint):
        if crease is None:
            faces.append(_orientedFace(list(points), hint))
            return
        i = 0 if crease == '02' else 1
        ring = [points[(i + k) % 4] for k in range(4)]
        faces.append(_orientedFace([ring[0], ring[1], ring[2]], hint))
        faces.append(_orientedFace([ring[0], ring[2], ring[3]], hint))

    horizontal(bottom, prism.resolvedBottomCrease(), (0.0, 0.0, -1.0))
    horizontal(top, prism.resolvedTopCrease(), (0.0, 0.0, 1.0))

    sideHints = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0),
                 (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0))
    for i in range(4):
        j = (i + 1) % 4
        quad = [bottom[i], bottom[j], top[j], top[i]]
        polygon = [p for k, p in enumerate(quad) if p != quad[k - 1]]
        if len(polygon) >= 3:
            faces.append(_orientedFace(polygon, sideHints[i]))
    return faces


def partFaces(part: Box) -> List[Face]:
    """Faces of any primitive shape, dispatched by type."""
    if isinstance(part, Prism):
        return prismFaces(part)
    return boxFaces(part)
