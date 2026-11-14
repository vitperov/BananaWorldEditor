# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Catalog-wide geometry invariants. Every test iterates over ALL catalog
# objects that declare primitive geometry, so adding a new object with
# geometry requires no test changes: the new object is validated
# automatically. No expected-geometry constants anywhere.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.commonModels.ObjectsCollection import ObjectsCollection
from modules.Geometry3D.MapToPrimitives import (convertSquare, SQUARE_SIZE,
                                                FLOOR_HEIGHT, FOOTPRINT_MARGIN)
from modules.Geometry3D.Primitives import EPSILON

ROTATIONS = ['0', '90', '180', '270']


def primitiveObjects():
    collection = ObjectsCollection([os.path.join(REPO_ROOT, 'mapObjects')])
    return [obj for obj in collection.objects.values()
            if obj.geometry is not None and obj.geometry.isPrimitives()]


def slotProperties(mapObject):
    """Fake additionalProperties: every declared texture slot gets a
    recognizable value, so texture resolution can be checked generically."""
    return {prop.name: f"tex_{prop.name}"
            for prop in mapObject.additional_properties
            if prop.type == 'texture'}


class GeometryDataInvariants(unittest.TestCase):
    """Validation of the authored object.json geometry data."""

    @classmethod
    def setUpClass(cls):
        cls.objects = primitiveObjects()

    def test_catalog_has_geometry_objects(self):
        # Guards the other tests against passing vacuously.
        self.assertTrue(self.objects,
                        "no catalog object declares primitive geometry")

    def test_part_sizes_are_positive(self):
        for obj in self.objects:
            for part in obj.geometry.parts:
                for axis, extent in enumerate(part.size):
                    self.assertGreater(extent, 0.0,
                                       f"{obj.name}: part {part} has non-positive "
                                       f"size on axis {axis}")

    def test_parts_stay_near_the_footprint(self):
        # Parts may leave the square: walls are centred on the grid line,
        # so half their thickness belongs to the neighbouring square. Only
        # grossly misplaced geometry is rejected (see FOOTPRINT_MARGIN).
        for obj in self.objects:
            bounds = (obj.w * SQUARE_SIZE, obj.h * SQUARE_SIZE, FLOOR_HEIGHT)
            for part in obj.geometry.parts:
                for axis in range(3):
                    self.assertGreaterEqual(
                        part.origin[axis], -FOOTPRINT_MARGIN - EPSILON,
                        f"{obj.name}: part {part} is far outside the footprint")
                    self.assertLessEqual(
                        part.maxCorner()[axis],
                        bounds[axis] + FOOTPRINT_MARGIN + EPSILON,
                        f"{obj.name}: part {part} is far outside the footprint")

    def test_texture_slots_are_declared(self):
        for obj in self.objects:
            declared = set(slotProperties(obj))
            for part in obj.geometry.parts:
                self.assertIn(part.textureSlot, declared,
                              f"{obj.name}: part references texture slot "
                              f"'{part.textureSlot}' not declared in "
                              f"additionalProperties")

    def test_parts_do_not_overlap(self):
        for obj in self.objects:
            parts = obj.geometry.parts
            for i in range(len(parts)):
                for j in range(i + 1, len(parts)):
                    self.assertFalse(
                        parts[i].intersects(parts[j]),
                        f"{obj.name}: parts {parts[i]} and {parts[j]} overlap")


class ConverterInvariants(unittest.TestCase):
    """Rotation and placement math of the square-to-boxes converter."""

    @classmethod
    def setUpClass(cls):
        cls.objects = primitiveObjects()

    def assertBoxListsEqual(self, actual, expected, message):
        self.assertEqual(len(actual), len(expected), message)
        for a, e in zip(actual, expected):
            self.assertTrue(a.approxEquals(e), f"{message}: {a} != {e}")

    def convert(self, obj, **kwargs):
        args = dict(x=0, y=0, z=0, w=obj.w, h=obj.h, rotation='0',
                    additionalProperties=slotProperties(obj))
        args.update(kwargs)
        return convertSquare(obj.geometry, **args)

    def test_four_rotations_are_identity(self):
        for obj in self.objects:
            centerX = obj.w * SQUARE_SIZE / 2.0
            centerY = obj.h * SQUARE_SIZE / 2.0
            for part in obj.geometry.parts:
                rotated = part
                for _ in range(4):
                    rotated = rotated.rotated90(centerX, centerY)
                self.assertTrue(rotated.approxEquals(part),
                                f"{obj.name}: 4 x 90 degrees is not identity "
                                f"for {part}")

    def test_converting_rotated_equals_rotating_converted(self):
        for obj in self.objects:
            centerX = obj.w * SQUARE_SIZE / 2.0
            centerY = obj.h * SQUARE_SIZE / 2.0
            base = self.convert(obj, rotation='0')
            for steps, rotation in enumerate(ROTATIONS):
                converted = self.convert(obj, rotation=rotation)
                expected = []
                for box in base:
                    for _ in range(steps):
                        box = box.rotated90(centerX, centerY)
                    expected.append(box)
                self.assertBoxListsEqual(
                    converted, expected,
                    f"{obj.name} at rotation {rotation}")

    def test_placement_is_pure_translation(self):
        for obj in self.objects:
            for rotation in ROTATIONS:
                atOrigin = self.convert(obj, rotation=rotation)
                placed = self.convert(obj, rotation=rotation, x=3, y=5, z=1)
                offset = (3 * SQUARE_SIZE, 5 * SQUARE_SIZE, 1 * FLOOR_HEIGHT)
                expected = [box.translated(offset) for box in atOrigin]
                self.assertBoxListsEqual(
                    placed, expected,
                    f"{obj.name} placed at (3, 5, 1) rotation {rotation}")

    def test_rotation_preserves_count_and_volume(self):
        for obj in self.objects:
            base = self.convert(obj, rotation='0')
            baseVolume = sum(box.volume() for box in base)
            for rotation in ROTATIONS:
                converted = self.convert(obj, rotation=rotation)
                self.assertEqual(len(converted), len(base),
                                 f"{obj.name}: rotation changed part count")
                self.assertAlmostEqual(
                    sum(box.volume() for box in converted), baseVolume,
                    msg=f"{obj.name}: rotation changed total volume")

    def test_rotated_parts_stay_near_the_footprint(self):
        # Rotation must not move geometry away from its square; the same
        # margin as the unrotated check applies (walls straddle the grid
        # line in every orientation).
        for obj in self.objects:
            if obj.w != obj.h:
                # A rotated rectangular footprint is not the original
                # footprint; this containment invariant only holds for
                # square ones.
                continue
            bounds = (obj.w * SQUARE_SIZE, obj.h * SQUARE_SIZE, FLOOR_HEIGHT)
            for rotation in ROTATIONS:
                for box in self.convert(obj, rotation=rotation):
                    for axis in range(3):
                        self.assertGreaterEqual(
                            box.origin[axis], -FOOTPRINT_MARGIN - EPSILON,
                            f"{obj.name} rotation {rotation}: {box} is far "
                            f"outside the footprint")
                        self.assertLessEqual(
                            box.maxCorner()[axis],
                            bounds[axis] + FOOTPRINT_MARGIN + EPSILON,
                            f"{obj.name} rotation {rotation}: {box} is far "
                            f"outside the footprint")

    def test_texture_slots_resolve_from_properties(self):
        for obj in self.objects:
            for rotation in ROTATIONS:
                for box in self.convert(obj, rotation=rotation):
                    self.assertEqual(box.texture, f"tex_{box.textureSlot}",
                                     f"{obj.name}: slot '{box.textureSlot}' "
                                     f"resolved to '{box.texture}'")

    def test_missing_property_resolves_to_none(self):
        for obj in self.objects:
            for box in self.convert(obj, additionalProperties={}):
                self.assertIsNone(box.texture,
                                  f"{obj.name}: texture resolved without "
                                  f"properties")


if __name__ == '__main__':
    unittest.main()
