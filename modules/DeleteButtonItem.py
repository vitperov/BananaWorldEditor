# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from pyqtgraph.Qt import QtCore, QtGui

class DeleteButtonItem(QObject):
    def __init__(self, painter, tilesize, col, row):
        QObject.__init__(self)

        self._painter = painter
        self._tilesize = tilesize
        self._col = col
        self._row = row

        size = QSize(self._tilesize, self._tilesize)

        self.updateState()


    def updateState(self):
        imgFile = "resources/redX.png"
        try:
            pixmap = QtGui.QPixmap(imgFile, "1")  # see: https://stackoverflow.com/questions/16990914/python-pyqt-qpixmap-returns-null-for-a-valid-image/17121857#17121857
        except:
            pixmap = QtGui.QPixmap(imgFile)
        size = QSize(self._tilesize, self._tilesize)

        scaledPixmap = pixmap.scaled(size, QtCore.Qt.KeepAspectRatio)
       
        x = self._col * self._tilesize
        y = self._row * self._tilesize
        
        self._painter.drawPixmap(x, y, scaledPixmap)
