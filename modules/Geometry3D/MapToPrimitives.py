# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Converts a placed map square into world-space boxes.
# Takes plain values rather than MapObjectModelGeneral so it stays free
# of Qt dependencies and works directly on map-file JSON.

from typing import Dict, List, Optional

from modules.Geometry3D.Primitives import Box
from modules.Geometry3D.ObjectGeometry import ObjectGeometry

# One 2D grid square is a 2 x 2 meter footprint; one floor is 3 meters.
SQUARE_SIZE = 2.0
FLOOR_HEIGHT = 3.0

_ROTATION_STEPS = {'0': 0, '90': 1, '180': 2, '270': 3}


def convertSquare(geometry: ObjectGeometry,
                  x: int, y: int, z: int,
                  w: int = 1, h: int = 1,
                  rotation: str = '0',
                  additionalProperties: Optional[Dict[str, str]] = None) -> List[Box]:
    """Return world-space boxes for one placed square.

    Geometry is authored at rotation 0 in square-local meters (origin at
    the square's min-x/min-y corner). The map rotation spins the parts
    around the footprint center, then the result is translated to the
    square's world position. Texture slots are resolved against the
    square's additionalProperties.
    """
    if not geometry.isPrimitives():
        raise ValueError(
            f"Geometry type '{geometry.geometryType}' is not convertible to primitives")

    # Accept plain strings from map JSON as well as the editor's
    # ObjectRotation enum, whose str() differs across Python versions.
    steps = _ROTATION_STEPS[str(getattr(rotation, 'value', rotation))]
    centerX = w * SQUARE_SIZE / 2.0
    centerY = h * SQUARE_SIZE / 2.0
    offset = (x * SQUARE_SIZE, y * SQUARE_SIZE, z * FLOOR_HEIGHT)
    properties = additionalProperties if additionalProperties is not None else {}

    boxes = []
    for part in geometry.parts:
        box = part
        for _ in range(steps):
            box = box.rotated90(centerX, centerY)
        box = box.translated(offset)
        box.texture = properties.get(box.textureSlot)
        boxes.append(box)
    return boxes
