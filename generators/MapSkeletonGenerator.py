# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import random

from modules.Terrain.MapEditHelper import *

TypeGrass  = "Grass"
TypeForest = "Forest"
TypeRoad   = "Road"

class MapSkeletonGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)
        self.fogModel = 'Fog'

        self._editor = MapEditHelper(mapModel)

        self._w = None
        self._h = None

    def generate(self):
        print("Generating empty map")

        def parseBool(var):
            if var.lower() == "false":
                return False
            elif var.lower() == "true":
                return True
            else:
                raise Exception("Unsupported boolean value: " + var)

        self.forestAroundMap = int(self.settings['forestAroundMap'])
        self.roadWidth       = int(self.settings['roadWidth'])
        self.leftExit        = parseBool(self.settings['leftExit'])
        self.rightExit       = parseBool(self.settings['rightExit'])
        self.landLotWidth    = int(self.settings['landLotWidth'])
        self.landLotHeight   = int(self.settings['landLotHeight'])
        self.landLotsRows    = int(self.settings['landLotsRows'])
        self.landLotsColumns = int(self.settings['landLotsColumns'])

        self._calcMapSize()
        self.mapModel.newMap(self._w, self._h)

        self.fillEverythingGrass()
        self.genForestAroundMap()
        self.genRoad()
        
        self.genLandLots()
        
        self.mapModel.updateEntireMap()

        print("Done")

    def clear_generated(self):
        print("Clear generated Map Skeleton")
        print("Done nothing")

    def _calcMapSize(self):
        self._w = self.landLotWidth * self.landLotsColumns + 2 * self.forestAroundMap
        self._h = self.landLotHeight * self.landLotsRows + 2 * self.forestAroundMap + self.roadWidth

    def fillEverythingGrass(self):
        self._editor.fillArea(Point(0,0), AreaSize(self._w, self._h), 'model', TypeGrass)

    def genForestAroundMap(self):
        self._editor.fillAreaBorder(Point(0,0),  AreaSize(self._w, self._h),
            TypeForest, width=self.forestAroundMap)
            
    def genRoad(self):
        #FIXME: do road after every landLot height
        halfHeight = math.ceil(self._h / 2)

        leftMargin = 0
        rightMargin = 0
        if not self.leftExit:
            leftMargin = self.forestAroundMap
        if not self.rightExit:
            rightMargin = self.forestAroundMap

        self._editor.fillArea(Point(leftMargin, halfHeight - 1), AreaSize(self._w-(leftMargin + rightMargin), 2), 'model', TypeRoad)

    def genLandLots(self):
        for row in range(self.landLotsRows):
            for column in range(self.landLotsColumns):
                print("Generating LandLot. Row=" + str(row) + " column=" + str(column))
                startPt = Point(column * self.landLotWidth + self.forestAroundMap,
                                row * self.landLotHeight + self.forestAroundMap)

                if row != 0:
                    startPt.y += self.roadWidth

                print("    startPt=" + str(startPt))
                self.placeLandLot(startPt.x, startPt.y)

    def placeLandLot(self, x, y):
        obj = MapObjectModelGeneral()
        obj.init(x, y, "LandLot", ObjectRotation.deg0, self.landLotWidth, self.landLotHeight)
        self.mapModel.addMapObject(obj)
