# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Invariants of Geometry3D.GltfExport, checked over every catalog object
# with primitive geometry (no per-object expected bytes). The .glb files
# are written to a temp dir, read back with unpackGlb and inspected with
# plain struct/json — no third-party glTF library is involved, so a
# mistake in the writer cannot be masked by a matching reader.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import json
import os
import struct
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.commonModels.ObjectsCollection import ObjectsCollection
from modules.commonModels.TexturesCollection import TexturesCollection
from modules.Geometry3D.GltfExport import (exportCatalog, unpackGlb, slotOrder,
                                           toGltfPosition, MANIFEST_NAME,
                                           COMPONENT_FLOAT, COMPONENT_UNSIGNED_SHORT,
                                           COMPONENT_UNSIGNED_INT)

FACES_PER_BOX = 6
VERTICES_PER_FACE = 4
INDICES_PER_FACE = 6
COMPONENTS = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3}


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def readAccessor(document, binary, index):
    accessor = document['accessors'][index]
    view = document['bufferViews'][accessor['bufferView']]
    count = accessor['count']
    components = COMPONENTS[accessor['type']]
    fmt = {COMPONENT_FLOAT: 'f', COMPONENT_UNSIGNED_SHORT: 'H',
           COMPONENT_UNSIGNED_INT: 'I'}[accessor['componentType']]
    start = view['byteOffset'] + accessor.get('byteOffset', 0)
    flat = struct.unpack_from(f'<{count * components}{fmt}', binary, start)
    if components == 1:
        return list(flat)
    return [tuple(flat[i:i + components]) for i in range(0, len(flat), components)]


class GltfExportInvariants(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.objects = ObjectsCollection([os.path.join(REPO_ROOT, 'mapObjects')])
        cls.textures = TexturesCollection([os.path.join(REPO_ROOT, 'textures')])
        cls.tempDir = tempfile.TemporaryDirectory()
        cls.outDir = cls.tempDir.name
        cls.report = exportCatalog(cls.objects, cls.textures, cls.outDir)
        with open(os.path.join(cls.outDir, MANIFEST_NAME)) as file:
            cls.manifest = json.load(file)
        cls.exported = {}
        for name in cls.report.objects:
            with open(os.path.join(cls.outDir, cls.manifest['objects'][name]['file']), 'rb') as file:
                cls.exported[name] = unpackGlb(file.read())

    @classmethod
    def tearDownClass(cls):
        cls.tempDir.cleanup()

    def primitiveObjects(self):
        return [obj for obj in self.objects.objects.values()
                if obj.geometry is not None and obj.geometry.isPrimitives()]

    def test_every_primitive_object_is_exported_and_listed(self):
        names = sorted(obj.name for obj in self.primitiveObjects())
        self.assertTrue(names, "no catalog object declares primitive geometry")
        self.assertEqual(sorted(self.report.objects), names)
        self.assertEqual(sorted(self.manifest['objects']), names)
        self.assertEqual(self.report.skipped, [])

    def test_every_texture_is_copied_and_listed(self):
        names = sorted(self.textures.allTextureTypes())
        self.assertTrue(names)
        self.assertEqual(sorted(self.manifest['textures']), names)
        for name, relative in self.manifest['textures'].items():
            path = os.path.join(self.outDir, relative)
            self.assertTrue(os.path.isfile(path), f"{name}: {relative} missing")
            with open(path, 'rb') as copied, open(self.textures.getTextureFile(name), 'rb') as source:
                self.assertEqual(copied.read(), source.read())

    def test_glb_container_is_well_formed(self):
        for name, (document, binary) in self.exported.items():
            self.assertEqual(document['asset']['version'], '2.0')
            self.assertEqual(len(binary) % 4, 0, f"{name}: BIN chunk not 4-byte aligned")
            self.assertEqual(document['buffers'][0]['byteLength'], len(binary))
            for view in document['bufferViews']:
                self.assertEqual(view['byteOffset'] % 4, 0, f"{name}: misaligned bufferView")
                self.assertLessEqual(view['byteOffset'] + view['byteLength'], len(binary))
            # Scene -> node -> mesh chain is present, so viewers show something.
            node = document['nodes'][document['scenes'][document['scene']]['nodes'][0]]
            self.assertEqual(document['meshes'][node['mesh']]['name'], name)

    def test_one_primitive_and_material_per_texture_slot(self):
        for obj in self.primitiveObjects():
            document, _ = self.exported[obj.name]
            slots = slotOrder(obj.geometry)
            primitives = document['meshes'][0]['primitives']
            self.assertEqual(len(primitives), len(slots), obj.name)
            self.assertEqual(len(document['materials']), len(slots), obj.name)
            self.assertEqual(self.manifest['objects'][obj.name]['materialSlots'], slots)
            for index, (primitive, slot) in enumerate(zip(primitives, slots)):
                self.assertEqual(primitive['material'], index)
                self.assertEqual(document['materials'][index]['name'], slot)

    def test_vertex_and_index_counts_match_the_parts(self):
        for obj in self.primitiveObjects():
            document, binary = self.exported[obj.name]
            for primitive, slot in zip(document['meshes'][0]['primitives'], slotOrder(obj.geometry)):
                boxes = sum(1 for p in obj.geometry.parts if p.textureSlot == slot)
                positions = readAccessor(document, binary, primitive['attributes']['POSITION'])
                normals = readAccessor(document, binary, primitive['attributes']['NORMAL'])
                uvs = readAccessor(document, binary, primitive['attributes']['TEXCOORD_0'])
                indices = readAccessor(document, binary, primitive['indices'])
                self.assertEqual(len(positions), boxes * FACES_PER_BOX * VERTICES_PER_FACE)
                self.assertEqual(len(normals), len(positions))
                self.assertEqual(len(uvs), len(positions))
                self.assertEqual(len(indices), boxes * FACES_PER_BOX * INDICES_PER_FACE)
                self.assertLess(max(indices), len(positions))
                self.assertEqual(len(indices) % 3, 0)

    def test_position_bounds_match_the_rotated_parts(self):
        # Accessor min/max are mandatory for POSITION and must bound the
        # data; the data itself must be the parts rotated into glTF space.
        for obj in self.primitiveObjects():
            document, binary = self.exported[obj.name]
            for primitive, slot in zip(document['meshes'][0]['primitives'], slotOrder(obj.geometry)):
                parts = [p for p in obj.geometry.parts if p.textureSlot == slot]
                corners = []
                for box in parts:
                    lo, hi = box.origin, box.maxCorner()
                    corners.extend(toGltfPosition(c) for c in
                                   [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
                expectedMin = [min(c[i] for c in corners) for i in range(3)]
                expectedMax = [max(c[i] for c in corners) for i in range(3)]
                accessor = document['accessors'][primitive['attributes']['POSITION']]
                for axis in range(3):
                    self.assertAlmostEqual(accessor['min'][axis], expectedMin[axis], places=5)
                    self.assertAlmostEqual(accessor['max'][axis], expectedMax[axis], places=5)
                positions = readAccessor(document, binary, primitive['attributes']['POSITION'])
                for p in positions:
                    for axis in range(3):
                        self.assertGreaterEqual(p[axis], accessor['min'][axis] - 1e-6)
                        self.assertLessEqual(p[axis], accessor['max'][axis] + 1e-6)

    def test_triangles_face_their_normals_and_are_y_up(self):
        # Axis conversion must be a rotation: winding agrees with the
        # exported normals, normals are unit length, and the object's
        # height runs along glTF +Y.
        for obj in self.primitiveObjects():
            document, binary = self.exported[obj.name]
            for primitive in document['meshes'][0]['primitives']:
                positions = readAccessor(document, binary, primitive['attributes']['POSITION'])
                normals = readAccessor(document, binary, primitive['attributes']['NORMAL'])
                indices = readAccessor(document, binary, primitive['indices'])
                for t in range(0, len(indices), 3):
                    a, b, c = (positions[indices[t + k]] for k in range(3))
                    faceNormal = cross(sub(b, a), sub(c, a))
                    self.assertGreater(dot(faceNormal, normals[indices[t]]), 0.0, obj.name)
                for n in normals:
                    self.assertAlmostEqual(dot(n, n), 1.0, places=5)
                accessor = document['accessors'][primitive['attributes']['POSITION']]
                self.assertGreaterEqual(accessor['min'][1], -1e-6, f"{obj.name}: below ground in glTF Y")

    def test_uvs_are_flipped_into_gltf_convention(self):
        # glTF v = 0 is the image top: a point on the floor (editor z = 0)
        # must map to v = 1 on vertical faces.
        for obj in self.primitiveObjects():
            document, binary = self.exported[obj.name]
            for primitive in document['meshes'][0]['primitives']:
                positions = readAccessor(document, binary, primitive['attributes']['POSITION'])
                normals = readAccessor(document, binary, primitive['attributes']['NORMAL'])
                uvs = readAccessor(document, binary, primitive['attributes']['TEXCOORD_0'])
                for p, n, uv in zip(positions, normals, uvs):
                    if abs(n[1]) < 1e-6 and abs(p[1]) < 1e-6:   # vertical face, on the floor
                        self.assertAlmostEqual(uv[1], 1.0, places=5)

    def test_manifest_records_units_and_axes(self):
        self.assertEqual(self.manifest['units'], 'meters')
        self.assertEqual(self.manifest['squareSize'], 2.0)
        self.assertEqual(self.manifest['floorHeight'], 3.0)
        self.assertIn('gltf', self.manifest['axes'])


if __name__ == '__main__':
    unittest.main()
