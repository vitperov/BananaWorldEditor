# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from pyqtgraph.Qt import QtCore, QtGui

class MapItemDrawer:
    def __init__(self, model, painter, tilesize, objCollection):

        self._model = model
        self._objCollection = objCollection
        self._painter = painter
        self._tilesize = tilesize
        self._col = model.x
        self._row = model.y

        size = QSize(self._tilesize, self._tilesize)
        
        self.sqType = self._model.getProperty('model')
        isContour = objCollection.isContour(self.sqType)
        #print(f"{self.sqType} -> {isContour}")

        if isContour:
            self.drawContour()
        else:
            self.drawPixmap()

    def drawPixmap(self):
        if self.sqType == "None":
            return

        rotation    = self._model.getProperty('rotation')

        imgFile = self._objCollection.getIcon(self.sqType)
        try:
            pixmap = QtGui.QPixmap(imgFile, "1") # see: https://stackoverflow.com/questions/16990914/python-pyqt-qpixmap-returns-null-for-a-valid-image/17121857#17121857
        except:
            pixmap = QtGui.QPixmap(imgFile)

        transform = QtGui.QTransform().rotate(int(rotation))
        rotatedPixmap = pixmap.transformed(transform, QtCore.Qt.SmoothTransformation)

        size = QSize(self._tilesize, self._tilesize)
        scaledPixmap = rotatedPixmap.scaled(size, QtCore.Qt.KeepAspectRatio)

        x = self._col * self._tilesize
        y = self._row * self._tilesize
        
        self._painter.drawPixmap(x, y, scaledPixmap)
        
    def drawContour(self):
        if self.sqType == "None":
            return

        sqTypeDescription = self._objCollection.getObject(self.sqType)
        contourColor = sqTypeDescription.contour

        x = self._col * self._tilesize
        y = self._row * self._tilesize
        
        rotatedSize = self._model.getSize()
        width = rotatedSize.w * self._tilesize
        height = rotatedSize.h * self._tilesize

        color = QtGui.QColor(contourColor)

        self._painter.setPen(QtGui.QPen(color, 2))  # Set pen color and thickness

        # Draw the rectangle contour
        #print(f"{sqType} -> {contourColor} -> {x} {y} {width} {height}")
        self._painter.drawRect(x, y, width, height)
