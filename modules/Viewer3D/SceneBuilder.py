# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Builds the 3D scene (a list of world-space boxes) for a map model.
# Objects without primitive geometry are skipped: they are not
# renderable yet (furniture etc. will arrive as imported meshes).

from typing import List

from modules.Geometry3D.Primitives import Box
from modules.Geometry3D.MapToPrimitives import convertSquare, SQUARE_SIZE


def buildMapBoxes(mapModel) -> List[Box]:
    objCollection = mapModel.getObjectsCollection()
    boxes = []

    for square in mapModel.getSquares():
        modelName = square.getProperty('model')
        mapObject = objCollection.getObject(modelName)
        if mapObject is None or mapObject.geometry is None:
            continue
        if not mapObject.geometry.isPrimitives():
            continue

        properties = {prop.name: prop.value
                      for prop in square.additional_properties}
        boxes.extend(convertSquare(mapObject.geometry,
                                   square.x, square.y, square.z,
                                   w=square.w, h=square.h,
                                   rotation=square.getProperty('rotation'),
                                   additionalProperties=properties))

    # Thin ground slab under the whole map, so the scene has a floor to
    # stand on even before Floor objects get geometry.
    if mapModel.width > 0 and mapModel.height > 0:
        boxes.append(Box(origin=(0.0, 0.0, -0.1),
                         size=(mapModel.width * SQUARE_SIZE,
                               mapModel.height * SQUARE_SIZE,
                               0.1)))

    return boxes
