# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.GeometryPrimitives import *

class MapEditHelper():
    def __init__(self, model):
        self._model = model

    def fillArea(self, startPt, size, property, value):
        for y in range(startPt.y, startPt.y + size.h):
            for x in range(startPt.x, startPt.x + size.w):
                square = self._model.getSquare(x, y)
                square.setProperty(property, value)

    def fillAreaBorder(self, startPt, size, type, width=1):
        self.fillArea(startPt,                                      AreaSize(size.w, width), 'model', type)
        self.fillArea(Point(startPt.x ,startPt.y + size.h - width), AreaSize(size.w, width), 'model', type)
        self.fillArea(startPt,                                      AreaSize(width, size.h), 'model', type)
        self.fillArea(Point(startPt.x + size.w - width, startPt.y), AreaSize(width, size.h), 'model', type)
