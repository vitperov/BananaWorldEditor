# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Builds the 3D scene for a map model: a list of world-space boxes plus
# the image file for every texture name those boxes reference.
# Objects without primitive geometry are skipped: they are not
# renderable yet (furniture etc. will arrive as imported meshes).

from typing import Dict, List, Optional

from modules.Geometry3D.Primitives import Box
from modules.Geometry3D.MapToPrimitives import convertSquare, SQUARE_SIZE


class Scene:
    """boxes: world-space boxes; textureFiles: texture name -> image path
    (None when the map names a texture the catalog does not have, so the
    viewer can show a stand-in color instead of failing)."""

    def __init__(self, boxes: List[Box], textureFiles: Dict[str, Optional[str]]):
        self.boxes = boxes
        self.textureFiles = textureFiles


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


def resolveTextureFiles(boxes: List[Box], texturesCollection) -> Dict[str, Optional[str]]:
    """Image path for every texture name the boxes reference.

    Unknown names (and every name when the map has no texture catalog)
    map to None rather than being dropped, so callers can tell "texture
    not set" from "texture set but missing from the catalog".
    """
    files = {}
    for box in boxes:
        if box.texture and box.texture not in files:
            files[box.texture] = (texturesCollection.getTextureFile(box.texture)
                                  if texturesCollection is not None else None)
    return files


def buildScene(mapModel) -> Scene:
    boxes = buildMapBoxes(mapModel)
    textureFiles = resolveTextureFiles(boxes, mapModel.getTexturesCollection())
    return Scene(boxes, textureFiles)
