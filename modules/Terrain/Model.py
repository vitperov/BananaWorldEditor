# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from enum import Enum
from PyQt5.QtCore import *

from modules.commonModels.MapModelGeneral import *
from modules.commonModels.ObjectsCollection import *
from modules.GeneratorPluginsModel.GeneratorPluginsLoader import *
from modules.ApplicationSettings.ApplicationSettingsModel import ApplicationSettingsModel

class Model:
    def __init__(self):
        settings = ApplicationSettingsModel()
        nativeMapObjectsDir   = os.path.join(os.getcwd(), 'mapObjects')
        externalMapObjectsDir = settings.getAdditionalMapObjectsDir()
        self.objCollection = ObjectsCollection([nativeMapObjectsDir, externalMapObjectsDir])
        #print("Map objects found: " + str(self.objCollection.allObjectTypes()))

        texturesCollection = None # Not implemented for Terrain
        self.map = MapModelGeneral(MapObjectModelGeneral, self.objCollection, texturesCollection)
        
        pluginsDir = 'generators'
        self.generators = GeneratorPluginsLoader(self.map)
        self.generators.loadPluginsFrom(pluginsDir)
        #print("Generator plugins found: " + str(self.generators.generators))
