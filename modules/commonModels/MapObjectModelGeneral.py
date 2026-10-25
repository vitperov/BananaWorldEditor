# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtCore import *

import traceback
import json

import uuid

from modules.GeometryPrimitives import *
from modules.commonModels.ObjectRotation import *

class AdditionalPropertyValue:
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

class MapObjectModelGeneral(QObject):
    changed = pyqtSignal()

    def __init__(self, id=None): # TODO FIX: why second init??
        QObject.__init__(self)
        self.classnames = dict()
        self.properties = dict()
        self.additional_properties: List[AdditionalPropertyValue] = []
        
        self.model = "Empty"

        self.classnames['rotation']  = ObjectRotation
        self.properties['rotation']  = ObjectRotation.deg0

        self.classnames['model']      = str
        self.properties['model']      = "Empty"

        self.id = str(id) if (id is not None) else str(uuid.uuid4())

        self.x = 0
        self.y = 0
        self.z = 0
        self.w = 1
        self.h = 1

    def init(self, x, y, model, rotation=ObjectRotation.deg0, w=1, h=1, id=None):
        self.id = str(id) if (id is not None) else str(uuid.uuid4()) # FIXED: id was missing
        self.x = x
        self.y = y
        self.z = 0

        self.properties['model']    = model
        self.properties['rotation'] = rotation
        self.w = w
        self.h = h

    def toSerializableObj(self):
        # properties are enums, they can't be directly converted to int
        obj = dict()
        for name, prop in self.properties.items():
            value = prop
            obj[name] = value

        obj['x'] =  self.x
        obj['y'] =  self.y
        obj['z'] =  self.z
        obj['w'] =  self.w
        obj['h'] =  self.h
        obj['id'] = self.id
        obj['model'] = self.properties['model']

        if self.additional_properties:
            obj['additionalProperties'] = {
                prop.name: prop.value for prop in self.additional_properties
            }

        return obj

    def getProperty(self, name):
        return self.properties[name]

    def setProperty(self, name, value):
        variableClass = self.classnames[name]
        self.properties[name] = variableClass(value)
        self.changed.emit()

    def getAdditionalProperties(self):
        return self.additional_properties

    def setAdditioanalProperty(self, name, value):
        for prop in self.additional_properties:
            if prop.name == name:
                prop.value = value
                self.changed.emit()
                return
        self.additional_properties.append(AdditionalPropertyValue(name, value))
        self.changed.emit()

    def deleteAdditionalProperty(self, name):
        """Remove one additional property by name. Returns True if it existed."""
        for i, prop in enumerate(self.additional_properties):
            if prop.name == name:
                del self.additional_properties[i]
                self.changed.emit()
                return True
        return False

    def clearAdditionalProperties(self):
        """Drop every additional property (resets additionalProperties to empty,
        so the key is omitted on save). Returns True if anything was removed."""
        if not self.additional_properties:
            return False
        self.additional_properties = []
        self.changed.emit()
        return True

    def restoreFromJson(self, js):
        self.x = js['x']
        self.y = js['y']
        self.z = js.get('z', 0)
        self.w = js.get('w', 1)
        self.h = js.get('h', 1)

        if ('id' in js) and (len(js['id'])) > 0:
            self.id = js['id']
        else:
            self.id = str(uuid.uuid4())

        for propName, propClass in self.classnames.items():
            self.properties[propName] = propClass(js.get(propName,""))

        additional_properties = js.get('additionalProperties', {})
        for name, value in additional_properties.items():
            self.setAdditioanalProperty(name, value) 

    def setSize(self, size):
        self.w = size.w
        self.h = size.h

    def getSize(self): # consider rotation
        size = AreaSize(self.w, self.h)
        rotation = int(self.properties['rotation'].value);
        rotatedSize = size.rotated(rotation)
        return rotatedSize
        
    def getStartPt(self):
        return Point(self.x, self.y)
        
    def setModel(self, model):
        self.properties['model'] = model
        
    def getModel(self):
        return self.properties['model']
