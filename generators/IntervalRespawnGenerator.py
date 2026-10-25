# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import random

from modules.GeometryPrimitives import *

TypeForest  = "Forest"
TypeHouse   = "House"

class IntervalRespawnGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)
        self.generatedModel = 'opponentRespawn'

    def generate(self):
        print("Generating interval respawns")

        def parseBool(var):
            if var.lower() == "false":
                return False
            elif var.lower() == "true":
                return True
            else:
                raise Exception("Unsupported boolean value: " + var)

        intervalX = int(self.settings['intervalX'])
        intervalY = int(self.settings['intervalY'])
        skipHouse = parseBool(self.settings['skipHouse'])

        for col in range(0, self.mapModel.width, intervalX):
            for row in range(0, self.mapModel.height, intervalY):
                if self.isForest(row, col):
                    continue

                if skipHouse and self.isHouse(row, col):
                    continue

                self.placeRespawn(row,col)

        self.mapModel.updateEntireMap()

        print("Done " + str(self.generatedModel))
        
    def clear_generated(self):
        #return super().clear_generated()
        print("Not implemented")

    def placeRespawn(self, row, col):
        obj = MapObjectModelGeneral()
        obj.init(col, row, self.generatedModel)
        self.mapModel.addMapObject(obj)

    def isForest(self, row, col):
        square = self.mapModel.getSquare(col, row)
        if square is None:
            return False
        sqType = square.getProperty('model')

        return sqType == TypeForest

    def isHouse(self, row, col):
        allHouses = self.mapModel.getAllObjectOfType(TypeHouse)
        for house in allHouses:
            #TODO: move to objModel::getRectangle()
            houseRect = Rectangle(Point(house.x, house.y), AreaSize(house.w, house.h))
            if houseRect.isPointInside(Point(col,row)):
                return True
        return False
