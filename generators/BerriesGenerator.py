# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import random

TypeGrass  = "Grass"
TypeBerries = 'Berries'

class BerriesGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)

    def generate(self):
        print("Generating berries")
        probability = float(self.settings['probability'])
        
        zLevel = 0
        allSquares = self.mapModel.getAllSquares(zLevel)
        for obj in allSquares:
            if obj.getModel() == TypeGrass:
                generate = (random() < probability)
                if generate:
                    self._placeBerries(obj.x, obj.y)

        self.mapModel.updateEntireMap()

    def clear_generated(self):
        zLevel = 0
        allSquares = self.mapModel.getAllSquares(zLevel)
        for square in allSquares:
            if square.getModel() == TypeBerries:
                self.mapModel.deleteSquareById(square.id)

        self.mapModel.updateEntireMap()

    def _placeBerries(self, x, y):
        obj = MapObjectModelGeneral()
        obj.init(x, y, model = TypeBerries)
        self.mapModel.addMapObject(obj)
