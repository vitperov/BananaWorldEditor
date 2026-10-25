# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeneratorPluginsModel.GeneratorPluginBase import *

from random import randrange, random

from modules.GeometryPrimitives import *
from modules.Terrain.MapEditHelper import *

TypeLandLot  = "LandLot"
TypeForest   = "Forest"
TypeGrass    = "Grass"

class LandLotContentGenerator(GeneratorPluginBase):
    def __init__(self, mapModel):
        super().__init__(mapModel)

    def generate(self):
        print("Generating landLotContent")
        houseProbability = float(self.settings['houseProbability'])
        houseModels = self.settings['houseModels'].split(',')

        landLots = self.mapModel.getAllObjectOfType(TypeLandLot)
        print("    found " + str(len(landLots)) + " land lots")
        for lot in landLots:
            startPt = Point(lot.x, lot.y)
            size    = AreaSize(lot.w, lot.h)
            generator = LandLotGenerator(self.mapModel, startPt, size)
            generator.generate(houseProbability, houseModels)

        self.mapModel.updateEntireMap()

        print("Done " + str(self.generatedModel))
        
    def clear_generated(self):
        landLots = self.mapModel.getAllObjectOfType(TypeLandLot)

        for lot in landLots:
            startPt = Point(lot.x, lot.y)
            size    = AreaSize(lot.w, lot.h)
            zLevel = 0
            selectionRange = SelectionRange.fromStartPointAndSize(startPt, size, zLevel)
            self.mapModel.overwriteEverythingWith(selectionRange, TypeGrass)
            
            # lot obj was deleted after overwriteEverythingWith(). Restore it
            self.mapModel.addMapObject(lot)

        self.mapModel.updateEntireMap()


class LandLotGenerator():
    def __init__(self, model, startPt, size):
        self.generatedModel = 'landLotContent'
        self.model = model
        self.editor = MapEditHelper(model)
        self.startPt = startPt
        self.landLotRect = Rectangle(Point(0,0), size)
        self.landLotKeepout = 1
        self.allowedRect = self.landLotRect.shrink(self.landLotKeepout)
        print("Shrinked rect=" + str(self.allowedRect))

        self.placedObjects = []

    def canPlaceObjectAt(self, objRect):
        for obj in self.placedObjects:
            objKeepout = obj.localRectWithKeepout()
            placeFail = objKeepout.isRectPartiallyInside(objRect)
            if placeFail:
                return False

        return True


    def generate(self, houseProbability, houseModels):
        generateHouse = (random() < houseProbability)
        if generateHouse:
            print("  Generating house")
            house = LandLotObject(self)
            house.generateObjVariant(houseModels, self.model._objCollection)

            self.placedObjects.append(house)
        else:
            print("  NOT generating house")


class LandLotLwObject():
    def __init__(self, landLot, localPos=None, size=None, keepout=0):
        self.landLot = landLot
        self.objKeepout = keepout
        self.localPos = localPos
        self.size = size

    def localPosition(self):
        return self.localPos

    def localRect(self):
        return Rectangle(copy(self.localPos), copy(self.size))

    def localRectWithKeepout(self):
        return self.localRect().expand(self.objKeepout)

    def globalPosition(self):
        return self.localPos + self.landLot.startPt

class LandLotObject(LandLotLwObject):
    def __init__(self, landLot):
        self.generatedModel = 'landLotContent'
        LandLotLwObject.__init__(self, landLot, keepout=1)

    def generate(self, size, objModelName):
        # can we pass landObj and get it's size?
        self.size = size

        attempts = 500
        placeOk = False
        while (not placeOk) and attempts > 0:
            attempts -= 1
            self.localPos = genRandomObjPlace(self.landLot.allowedRect, size)
            placeOk = self.landLot.canPlaceObjectAt(self.localRect())

        if attempts == 0:
            print("!!!! Error: you are trying to put an object where there is no place for it")
            return False

        print("    Obj placed at: " + str(self.localPos) + "; size=" + str(size))

        #obj = MapObjectModelGeneral()
        #obj.init(self.globalPosition().x, self.globalPosition().y, objModelName, ObjectRotation.deg0, size.w, size.h)
        zLevel = 0
        obj = self.landLot.model.createObjectAt(self.globalPosition().x, self.globalPosition().y, zLevel)
        obj.setModel(objModelName)
        obj.setSize(size)
        self._randomizeProperty(obj, 'rotation')
        #print("Adding map object: " + str(obj.toSerializableObj()))

        rotatedSize = obj.getSize()
        rotation = int(obj.properties['rotation'].value)
        print("Rotation " + str(rotation) + ": size=" + str(size) + " -> " + str(rotatedSize))

        #delete grass under the object
        zLevel = 0
        selectionRange = SelectionRange.fromStartPointAndSize(self.globalPosition(), rotatedSize, zLevel)
        self.landLot.model.deleteObjectsInSelection(selectionRange, TypeForest)
        self.landLot.model.deleteObjectsInSelection(selectionRange, TypeGrass)

        return True

    def _chooseObjVariant(self, objModelVariants):
        nVariants = len(objModelVariants)
        sumProbability = 1
        print(f"nVariants={nVariants}, sumProbability={sumProbability}")

        normalizationF = 1.0 / sumProbability

        rnd = random()
        accumulatedProbability = 0
        for variantIdx in range(nVariants):
            variant = objModelVariants[variantIdx]
            variantProbability = 1.0 / nVariants
            accumulatedProbability += variantProbability * normalizationF
            #print(str(rnd) + "-> [" + variant.modelName + "] = "+ str(variant.probability) + "/" + str(accumulatedProbability))
            if rnd < accumulatedProbability:
                return variantIdx

    def _randomizeProperty(self, obj, propertyName):
        prop = obj.properties[propertyName]
        propClass = type(prop)

        newValueIdx = randrange(len(propClass))
        allPossibleValues = list(propClass)
        newValueStr = allPossibleValues[newValueIdx].value
        print("Rotation = " + str(newValueIdx) + "/" + str(len(propClass)))
        newValue = propClass(newValueStr)
        obj.properties[propertyName] = newValue

    def generateObjVariant(self, objModelVariants, objCollection):
        variantIdx = self._chooseObjVariant(objModelVariants)
        objModelName = objModelVariants[variantIdx]
        map_object = objCollection.getObject(objModelName)
        if map_object is None:
            raise Exception("Object model variant not found: " + objModelName)
        
        self.generate(AreaSize(map_object.w, map_object.h), objModelName)

#TODO: move to some library
def genRandomObjPlace(landLotRect, objSize):
        x = randrange(landLotRect.pt.x, landLotRect.pt.x + landLotRect.sz.w - objSize.w)
        y = randrange(landLotRect.pt.y, landLotRect.pt.y + landLotRect.sz.h - objSize.h)
        return Point(x, y)
