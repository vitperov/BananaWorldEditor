# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Invariants of Geometry3D.BoxFaces: the face/UV generation shared by
# the 3D viewer and the exporters. Like test_geometry_invariants.py this
# iterates over all catalog objects with primitive geometry, plus a few
# synthetic boxes, and pins properties rather than coordinates.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.commonModels.ObjectsCollection import ObjectsCollection
from modules.Geometry3D.BoxFaces import (boxFaces, faceTangents, faceUV,
                                         Face, TEXTURE_REPEAT)
from modules.Geometry3D.MapToPrimitives import convertSquare, SQUARE_SIZE
from modules.Geometry3D.Primitives import Box, EPSILON

ROTATIONS = ['0', '90', '180', '270']
AXIS_NORMALS = [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0),
                (0.0, 1.0, 0.0), (0.0, 0.0, -1.0), (0.0, 0.0, 1.0)]


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def sampleBoxes():
    """Catalog objects at a few placements, plus synthetic boxes."""
    collection = ObjectsCollection([os.path.join(REPO_ROOT, 'mapObjects')])
    boxes = []
    for obj in collection.objects.values():
        if obj.geometry is None or not obj.geometry.isPrimitives():
            continue
        for rotation in ROTATIONS:
            boxes.extend(convertSquare(obj.geometry, 3, 5, 1,
                                       w=obj.w, h=obj.h, rotation=rotation))
    boxes.append(Box((-1.3, 0.7, -0.1), (7.0, 0.25, 0.1)))
    boxes.append(Box((0.0, 0.0, 0.0), (1.0, 1.0, 1.0)))
    return boxes


class FaceGeometry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.boxes = sampleBoxes()
        cls.assertTrue(cls.boxes, "no boxes to test")

    def test_six_faces_with_axis_normals(self):
        for box in self.boxes:
            faces = boxFaces(box)
            self.assertEqual(len(faces), 6)
            self.assertEqual(sorted(f.normal for f in faces), sorted(AXIS_NORMALS))

    def test_corners_lie_on_the_box_surface(self):
        for box in self.boxes:
            lo, hi = box.origin, box.maxCorner()
            for face in boxFaces(box):
                axis = [i for i in range(3) if face.normal[i] != 0][0]
                plane = hi[axis] if face.normal[axis] > 0 else lo[axis]
                for corner in face.corners:
                    self.assertAlmostEqual(corner[axis], plane)
                    for i in range(3):
                        self.assertGreaterEqual(corner[i], lo[i] - EPSILON)
                        self.assertLessEqual(corner[i], hi[i] + EPSILON)

    def test_triangles_wind_counter_clockwise_from_outside(self):
        # Both triangles of every face must face along the outward normal,
        # so back-face culling (if ever enabled) hides the inside.
        for box in self.boxes:
            for face in boxFaces(box):
                indices = Face.TRIANGLE_INDICES
                for t in range(0, len(indices), 3):
                    a, b, c = (face.corners[indices[t + k]] for k in range(3))
                    triNormal = cross(sub(b, a), sub(c, a))
                    self.assertGreater(dot(triNormal, face.normal), 0.0,
                                       f"{box}: triangle {t // 3} of face "
                                       f"{face.normal} winds the wrong way")


class FaceUVs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.boxes = sampleBoxes()

    def test_tangents_are_right_handed_for_every_normal(self):
        # u grows to the right and v upward as seen from outside: the
        # texture is never mirrored on any side.
        for normal in AXIS_NORMALS:
            tangentU, tangentV = faceTangents(normal)
            self.assertEqual(cross(tangentU, tangentV), normal)
            self.assertAlmostEqual(dot(tangentU, tangentV), 0.0)
            self.assertAlmostEqual(dot(tangentU, normal), 0.0)

    def test_vertical_faces_grow_v_with_height(self):
        for normal in AXIS_NORMALS:
            if normal[2] != 0:
                continue
            _, tangentV = faceTangents(normal)
            self.assertEqual(tangentV, (0.0, 0.0, 1.0))
            # The image's bottom row (v = 0) sits on the ground plane.
            self.assertAlmostEqual(faceUV((4.2, -7.5, 0.0), normal)[1], 0.0)

    def test_uv_extent_tiles_by_world_size(self):
        # A face w x h meters spans w/R x h/R texture repeats: a 3 m high
        # wall shows 1.5 copies, never one stretched copy.
        for box in self.boxes:
            for face in boxFaces(box):
                tangentU, tangentV = faceTangents(face.normal)
                us = [uv[0] for uv in face.uvs]
                vs = [uv[1] for uv in face.uvs]
                widthU = sum(abs(tangentU[i]) * box.size[i] for i in range(3))
                widthV = sum(abs(tangentV[i]) * box.size[i] for i in range(3))
                self.assertAlmostEqual(max(us) - min(us), widthU / TEXTURE_REPEAT)
                self.assertAlmostEqual(max(vs) - min(vs), widthV / TEXTURE_REPEAT)

    def test_uv_is_affine_in_world_position(self):
        # Between any two corners of a face the UV difference equals the
        # projected position difference; this is what makes the texture
        # unstretched and continuous across coplanar boxes.
        for box in self.boxes:
            for face in boxFaces(box):
                tangentU, tangentV = faceTangents(face.normal)
                for i in range(4):
                    for j in range(4):
                        d = sub(face.corners[j], face.corners[i])
                        du = face.uvs[j][0] - face.uvs[i][0]
                        dv = face.uvs[j][1] - face.uvs[i][1]
                        self.assertAlmostEqual(du, dot(d, tangentU) / TEXTURE_REPEAT)
                        self.assertAlmostEqual(dv, dot(d, tangentV) / TEXTURE_REPEAT)

    def test_coplanar_neighbours_continue_the_texture(self):
        # The same object in two adjacent squares: wherever two faces with
        # the same normal share a corner position, they share the UV, so
        # a wall running across squares has no seam.
        collection = ObjectsCollection([os.path.join(REPO_ROOT, 'mapObjects')])
        shared = 0
        for obj in collection.objects.values():
            if obj.geometry is None or not obj.geometry.isPrimitives():
                continue
            for rotation in ROTATIONS:
                faces = []
                for x in (0, 1):
                    for box in convertSquare(obj.geometry, x, 0, 0,
                                             w=obj.w, h=obj.h, rotation=rotation):
                        faces.extend(boxFaces(box))
                byCorner = {}
                for face in faces:
                    for corner, uv in zip(face.corners, face.uvs):
                        key = (face.normal, tuple(round(c, 9) for c in corner))
                        if key in byCorner:
                            shared += 1
                            self.assertAlmostEqual(byCorner[key][0], uv[0])
                            self.assertAlmostEqual(byCorner[key][1], uv[1])
                        else:
                            byCorner[key] = uv
        # Small objects (a pillar) never touch their neighbour; walls do.
        # Guard against the loop passing vacuously for the whole catalog.
        self.assertGreater(shared, 0, "no catalog object shares corners "
                                      "with its neighbour")

    def test_texture_pattern_is_grid_aligned(self):
        # Moving a box by whole squares changes UVs by whole repeats, so
        # every square sees the texture at the same phase.
        for box in self.boxes:
            moved = box.translated((2 * SQUARE_SIZE, -SQUARE_SIZE, 0.0))
            for face, movedFace in zip(boxFaces(box), boxFaces(moved)):
                for uv, movedUV in zip(face.uvs, movedFace.uvs):
                    for a, b in zip(uv, movedUV):
                        self.assertAlmostEqual(a - b, round(a - b))


if __name__ == '__main__':
    unittest.main()
