# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from modules.GeometryPrimitives import *
from modules.Terrain.MapEditHelper import *

TypeForest   = "Forest"
TypeGrass    = "Grass"
TypeLandLot  = "LandLot"

class FixGrassUnderHouse(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)

    def generate(self):
        print("Fixing grass under large objects")

        allObjects = self.mapModel.getAllObjectOfType(None, selectionRange=None)
        largeObjects = list(filter(lambda obj: obj.getSize().w >= 2 and obj.getSize().h >= 2 and 
                                   obj.getModel() != TypeLandLot, allObjects))
        
        print(f"    found {len(largeObjects)} large objects")

        for obj in largeObjects:
            startPoint = Point(obj.x, obj.y)
            size = obj.getSize()
            zLevel = 0
            selectionRange = SelectionRange.fromStartPointAndSize(startPoint, size, zLevel)
            self.mapModel.deleteObjectsInSelection(selectionRange, TypeGrass)

        self.mapModel.updateEntireMap()

        print("Done fixing grass under large objects")
        
    def clear_generated(self):
        print("Clear operation is not applicable for grass fixing.")
