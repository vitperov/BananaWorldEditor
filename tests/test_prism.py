# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Invariants of the prism primitive (box with a height per footprint
# corner: wedges, hips, valleys, sloped slabs): face generation,
# winding, UV rules on slopes, creases, rotation and parsing.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import math
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.Geometry3D.BoxFaces import (boxFaces, partFaces, prismFaces,
                                         TEXTURE_REPEAT)
from modules.Geometry3D.GltfExport import buildGltf
from modules.Geometry3D.ObjectGeometry import ObjectGeometry
from modules.Geometry3D.Primitives import Box, Prism


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def samplePrisms():
    origin, size = (1.0, -2.0, 3.0), (2.3, 2.0, 1.5)
    flat = (0.0, 0.0, 0.0, 0.0)
    prisms = [Prism(origin, size, flat, (1.5, 1.5, 1.5, 1.5))]   # box
    for i in range(4):                                            # wedges
        top = [0.0] * 4
        top[i] = top[(i + 1) % 4] = 1.5
        prisms.append(Prism(origin, size, flat, top))
    for i in range(4):                                            # hips
        top = [0.0] * 4
        top[i] = 1.5
        prisms.append(Prism(origin, size, flat, top))
    prisms.append(Prism(origin, size, flat, (1.5, 0.1, 1.5, 1.5),
                        topCrease='13'))                          # valley
    prisms.append(Prism(origin, size, (0.0, 0.0, 1.0, 1.0),
                        (0.2, 0.2, 1.2, 1.2)))                    # slab
    return prisms


def solidVolume(faces):
    """Volume via the divergence theorem over the triangulated surface."""
    total = 0.0
    for face in faces:
        indices = face.triangleIndices
        for t in range(0, len(indices), 3):
            a, b, c = (face.corners[indices[t + k]] for k in range(3))
            total += dot(a, cross(b, c)) / 6.0
    return total


class PrismFaces(unittest.TestCase):

    def test_corners_stay_in_the_bounding_box(self):
        for prism in samplePrisms():
            lo, hi = prism.origin, prism.maxCorner()
            for face in prismFaces(prism):
                self.assertIn(len(face.corners), (3, 4))
                for corner in face.corners:
                    for axis in range(3):
                        self.assertGreaterEqual(corner[axis], lo[axis] - 1e-9)
                        self.assertLessEqual(corner[axis], hi[axis] + 1e-9)

    def test_normals_are_unit_and_match_winding(self):
        for prism in samplePrisms():
            for face in prismFaces(prism):
                self.assertAlmostEqual(dot(face.normal, face.normal), 1.0)
                indices = face.triangleIndices
                for t in range(0, len(indices), 3):
                    a, b, c = (face.corners[indices[t + k]] for k in range(3))
                    area = cross(sub(b, a), sub(c, a))
                    self.assertGreater(dot(area, face.normal), 0.0,
                                       f"{prism}: degenerate or flipped triangle")

    def test_faces_are_watertight(self):
        # Every directed triangle edge has exactly one opposite twin,
        # so the solid is closed and consistently wound.
        for prism in samplePrisms():
            edges = {}
            for face in prismFaces(prism):
                indices = face.triangleIndices
                for t in range(0, len(indices), 3):
                    tri = [face.corners[indices[t + k]] for k in range(3)]
                    for i in range(3):
                        edge = (tri[i], tri[(i + 1) % 3])
                        edges[edge] = edges.get(edge, 0) + 1
            for (a, b), count in edges.items():
                opposite = edges.get((b, a), 0)
                self.assertEqual(count, opposite,
                                 f"{prism}: unmatched edge {a}-{b}")

    def test_volume_matches_the_face_mesh(self):
        for prism in samplePrisms():
            self.assertAlmostEqual(prism.volume(),
                                   solidVolume(prismFaces(prism)), msg=prism)

    def test_full_height_prism_equals_its_box(self):
        prism = Prism((1.0, 2.0, 3.0), (2.0, 1.0, 1.5),
                      (0.0,) * 4, (1.5,) * 4)
        box = Box((1.0, 2.0, 3.0), (2.0, 1.0, 1.5))
        self.assertAlmostEqual(prism.volume(), box.volume())
        prismSet = {tuple(sorted(f.corners)) for f in prismFaces(prism)}
        boxSet = {tuple(sorted(f.corners)) for f in boxFaces(box)}
        self.assertEqual(prismSet, boxSet)

    def test_crease_defaults_bulge_outward_and_can_be_forced(self):
        hip = Prism((0, 0, 0), (2, 2, 3), (0,) * 4, (0, 0, 3, 0))
        self.assertEqual(hip.resolvedTopCrease(), '02')
        valley = Prism((0, 0, 0), (2, 2, 3), (0,) * 4, (3, 0, 3, 3))
        self.assertEqual(valley.resolvedTopCrease(), '02')  # default: ridge
        forced = Prism((0, 0, 0), (2, 2, 3), (0,) * 4, (3, 0, 3, 3),
                       topCrease='13')
        self.assertEqual(forced.resolvedTopCrease(), '13')
        self.assertLess(forced.volume(), valley.volume())

    def test_slope_uvs_keep_courses_level_and_unstretched(self):
        # On a sloped face, UV distance equals surface distance, and u
        # does not drift on a move with no horizontal travel.
        for prism in samplePrisms():
            for face in prismFaces(prism):
                if abs(face.normal[2]) in (0.0, 1.0):
                    continue
                for i in range(len(face.corners)):
                    for j in range(i + 1, len(face.corners)):
                        d = sub(face.corners[j], face.corners[i])
                        du = face.uvs[j][0] - face.uvs[i][0]
                        dv = face.uvs[j][1] - face.uvs[i][1]
                        self.assertAlmostEqual(
                            math.sqrt(dot(d, d)),
                            math.sqrt(du * du + dv * dv) * TEXTURE_REPEAT)
                        if abs(d[0]) + abs(d[1]) < 1e-12:
                            self.assertAlmostEqual(du, 0.0)

    def test_adjacent_slopes_continue_the_texture(self):
        # Two wedge prisms side by side along the eave form one plane;
        # shared corners must get identical UVs so the tiles continue.
        a = Prism((0.0, 0.0, 3.0), (2.0, 2.0, 3.0), (0.0,) * 4, (0, 0, 3, 3))
        b = Prism((2.0, 0.0, 3.0), (2.0, 2.0, 3.0), (0.0,) * 4, (0, 0, 3, 3))
        slopes = [face for part in (a, b) for face in prismFaces(part)
                  if 0.0 < abs(face.normal[2]) < 1.0]
        self.assertEqual(len(slopes), 2)
        uvByCorner = {}
        for face in slopes:
            for corner, uv in zip(face.corners, face.uvs):
                if corner in uvByCorner:
                    self.assertEqual(uvByCorner[corner], uv)
                uvByCorner[corner] = uv
        self.assertEqual(len([c for c in uvByCorner if c[0] == 2.0]), 2)

    def test_rotation_cycles_and_rotates_the_faces(self):
        for prism in samplePrisms():
            rotated = prism
            for _ in range(4):
                rotated = rotated.rotated90(1.0, -1.0)
            self.assertTrue(rotated.approxEquals(prism, 1e-9), prism)
            self.assertAlmostEqual(prism.volume(),
                                   prism.rotated90(1.0, -1.0).volume())

            rotated = prism.rotated90(1.0, -1.0)

            def rot(p):
                return (1.0 - (p[1] + 1.0), -1.0 + (p[0] - 1.0), p[2])

            expected = sorted(sorted(rot(c) for c in face.corners)
                              for face in prismFaces(prism))
            actual = sorted(sorted(face.corners)
                            for face in prismFaces(rotated))
            for e, a in zip(expected, actual):
                for ec, ac in zip(e, a):
                    for x, y in zip(ec, ac):
                        self.assertAlmostEqual(x, y, msg=prism)

    def test_parse_dispatch_and_export(self):
        geometry = ObjectGeometry.from_json({
            'type': 'primitives',
            'parts': [
                {'shape': 'prism', 'origin': [0, 0, 0], 'size': [2, 2, 3],
                 'bottom': [0, 0, 0, 0], 'top': [0, 0, 3, 3],
                 'textureSlot': 'externalTexture'},
                {'shape': 'prism', 'origin': [2, 0, 0], 'size': [2, 2, 3],
                 'bottom': [0, 0, 0, 0], 'top': [0, 0, 3, 0],
                 'topCrease': '02', 'textureSlot': 'externalTexture'},
            ]}, base_path='.')
        self.assertIsInstance(geometry.parts[0], Prism)
        self.assertEqual(len(partFaces(geometry.parts[0])), 5)
        document, binary = buildGltf('RoofTest', geometry)
        self.assertEqual(len(document['meshes'][0]['primitives']), 1)
        self.assertGreater(len(binary), 0)
        for bad in (
            {'shape': 'prism', 'origin': [0, 0, 0], 'size': [1, 1, 1],
             'bottom': [0, 0, 0], 'top': [1, 1, 1, 1]},
            {'shape': 'prism', 'origin': [0, 0, 0], 'size': [1, 1, 1],
             'bottom': [0, 0, 0, 0], 'top': [1, 1, 2, 1]},
            {'shape': 'prism', 'origin': [0, 0, 0], 'size': [1, 1, 1],
             'bottom': [0.5, 0, 0, 0], 'top': [0.4, 1, 1, 1]},
            {'shape': 'prism', 'origin': [0, 0, 0], 'size': [1, 1, 1],
             'bottom': [0, 0, 0, 0], 'top': [1, 1, 1, 1], 'topCrease': 'x'},
        ):
            with self.assertRaises(ValueError, msg=bad):
                ObjectGeometry.from_json(
                    {'type': 'primitives', 'parts': [bad]}, base_path='.')


if __name__ == '__main__':
    unittest.main()
