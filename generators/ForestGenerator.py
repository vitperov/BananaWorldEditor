# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import randrange, random

from modules.GeometryPrimitives import *
from modules.Terrain.MapEditHelper import *

TypeLandLot  = "LandLot"
TypeForest   = "Forest"
TypeGrass    = "Grass"

class ForestGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)

    def generate(self):
        print("Generating landLot Forest")
        forestProbability = float(self.settings['forestProbability'])

        landLots = self.mapModel.getAllObjectOfType(TypeLandLot)
        print("    found " + str(len(landLots)) + " land lots")
        for lot in landLots:
            startPt = Point(lot.x, lot.y)
            size    = AreaSize(lot.w, lot.h)
            generator = ForestGeneratorHelper(self.mapModel, startPt, size)
            generator.findAllOccupiedSquares()
            generator.generate(forestProbability)

        self.mapModel.updateEntireMap()

        print("Done " + str(self.generatedModel))
        
    def clear_generated(self):
        landLots = self.mapModel.getAllObjectOfType(TypeLandLot)

        for lot in landLots:
            startPt = Point(lot.x, lot.y)
            size    = AreaSize(lot.w, lot.h)
            zLevel = 0
            selectionRange = SelectionRange.fromStartPointAndSize(startPt, size, zLevel)
            # Forest -> Grass
            self.mapModel.setGroupProperty(selectionRange, TypeForest, "model", TypeGrass)
            
        self.mapModel.updateEntireMap()

class ForestGeneratorHelper():
    def __init__(self, model, startPt, size):
        self.model = model
        self.editor = MapEditHelper(model)
        self.startPt = startPt
        self.size = size
        self.zLevel = 0
        self.largeObjsKeepout = 1;

        self.occupiedSquares = []

    def findAllOccupiedSquares(self):
        selectionRange = SelectionRange.fromStartPointAndSize(self.startPt, self.size, 0)
        objects = self.model.getAllObjectOfType(None, selectionRange)
        
        for obj in objects:
            objModel = obj.properties.get('model')
            if objModel != TypeGrass and objModel != TypeLandLot:
                objStart = Point(obj.x, obj.y)
                size = obj.getSize()
                if size.w > 1 and size.h > 1:
                    size.w += 2 * self.largeObjsKeepout
                    size.h += 2 * self.largeObjsKeepout
                    objStart -= Point(self.largeObjsKeepout, self.largeObjsKeepout)
                    
                for x in range(objStart.x, objStart.x + size.w):
                    for y in range(objStart.y, objStart.y + size.h):
                        self.occupiedSquares.append(Point(x, y))

    def generate(self, forestProbability):
        for x in range(self.startPt.x, self.startPt.x + self.size.w):
            for y in range(self.startPt.y, self.startPt.y + self.size.h):
                if Point(x, y) not in self.occupiedSquares:
                    generateTree = (random() < forestProbability)
                    if generateTree:
                        squareItems = self.model.getSquareItems(x, y, self.zLevel)
                        for obj in squareItems:
                            if obj.getModel() == TypeGrass:
                                obj.setModel(TypeForest)
