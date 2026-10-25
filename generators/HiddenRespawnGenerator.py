# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import random

TypeForest  = "Forest"

class HiddenRespawnGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)
        self.generatedModel = 'opponentRespawn'

    def generate(self):
        print("Generating hidden respawns")
        # Find squares surrounded by trees. There can be 8 squares of forest maximum,
        # and don't forget to have at least one square to get out.
        minForest = int(self.settings['minForestAround'])
        maxForest = int(self.settings['maxForestAround'])
        def isForest(row, col):
            if row < 0:
                return False
            if row >= self.mapModel.height:
                return False
            if col < 0:
                return False
            if col >= self.mapModel.width:
                return False

            square = self.mapModel.getSquare(col, row)
            sqType = square.getProperty('model')

            return sqType == TypeForest


        def isHiddenSquare(row, col):
            if isForest(row, col):
                return False; # respawn can't be in the square with a tree

            forestSquares = 0;
            for r in [row-1, row, row+1]:
                for c in [col-1, col, col+1]:
                    if isForest(r, c):
                        forestSquares += 1

            return (forestSquares >= minForest) and (forestSquares <= maxForest)

        for col in range(self.mapModel.width):
            for row in range(self.mapModel.height):
                if isHiddenSquare(row, col):
                    self.placeRespawn(row,col)

        self.mapModel.updateEntireMap()

        print("Done " + str(self.generatedModel))
        
    def clear_generated(self):
        return super().clear_generated()

    def placeRespawn(self, row, col):
        obj = MapObjectModelGeneral()
        obj.init(col, row, model=self.generatedModel)
        self.mapModel.addMapObject(obj)
