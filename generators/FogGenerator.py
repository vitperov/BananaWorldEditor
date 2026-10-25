# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import random

TypeGrass  = "Grass"

class FogGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)
        self.generatedModel = 'Fog'


    def generate(self):
        print("Generating fog")
        interval = int(self.settings['intervalSquares'])

        for col in range(0, self.mapModel.width, interval):
            for row in range(0, self.mapModel.height, interval):
                self._placeFog(row,col)

        self.mapModel.updateEntireMap()

        print("Done " + str(self.generatedModel))

    def clear_generated(self):
        return super().clear_generated()

    def _placeFog(self, row, col):
        obj = MapObjectModelGeneral()
        obj.init(col, row, model = self.generatedModel)
        self.mapModel.addMapObject(obj)
