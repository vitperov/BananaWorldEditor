# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from modules.MapItemDrawer import *
from modules.DeleteButtonItem import *

import math
from modules.commonModels.SelectionRange import *

class MapWidget(QWidget):
    deleteRow         = pyqtSignal(int)
    deleteColumn      = pyqtSignal(int)
    selectionChanged  = pyqtSignal(SelectionRange)

    def __init__(self):
        QWidget.__init__(self)
        self._model = None

        self._layout = QVBoxLayout()
        self._model = None

        self.setLayout(self._layout)

        self.label = QtWidgets.QLabel()
        self.label.mousePressEvent = self.onMousePress
        self.label.mouseReleaseEvent = self.onMouseRelease

        self._canvas = QtGui.QPixmap(640, 480)
        self._canvas.fill(Qt.white)

        self._layout.addWidget(self.label)
        self._layout.addStretch()

        self.selectionRange = SelectionRange(None, None, None, None, 0)

        self.label.setPixmap(self._canvas)

    def onMousePress(self, event):
        x = event.pos().x()
        y = event.pos().y()
        self.selectionRange.startCol = int(x / self.pixPerTile)
        self.selectionRange.startRow = int(y / self.pixPerTile)

    def onMouseRelease(self, event):
        if self.selectionRange.startRow is None or self.selectionRange.startCol is None:
            return

        x2 = event.pos().x()
        y2 = event.pos().y()

        print(f"Mouse press point: ({self.selectionRange.startCol * self.pixPerTile}, {self.selectionRange.startRow * self.pixPerTile})")
        print(f"Mouse release point: ({x2}, {y2})")

        self.selectionRange.endCol = int(x2 / self.pixPerTile)
        self.selectionRange.endRow = int(y2 / self.pixPerTile)

        print(f"Selected area converted to cell coordinates: Start({self.selectionRange.startCol}, {self.selectionRange.startRow}), End({self.selectionRange.endCol}, {self.selectionRange.endRow})")

        [rows, cols] = self._model.size()

        if self.selectionRange.startRow < rows and self.selectionRange.startCol < cols:
            self.selectionChanged.emit(self.selectionRange)
                
        elif self.selectionRange.startRow == rows and self.selectionRange.startCol == cols:
            print("Clicked corner. No actions")
        elif self.selectionRange.startRow == rows:
            print("Delete column idx=" + str(self.selectionRange.startCol))
            self.deleteColumn.emit(self.selectionRange.startCol)
        elif self.selectionRange.startCol == cols:
            print("Delete row idx=" + str(self.selectionRange.startRow))
            self.deleteRow.emit(self.selectionRange.startRow)

        self.redrawAll()

    def setModel(self, model):
        self._model = model

    def addColumn(self, before):
        index = self.selectionRange.startCol
        if index is not None:
            if before:
                self._model.addColumn(index)
            else:
                self._model.addColumn(index + 1)

    def addRow(self, before):
        index = self.selectionRange.startRow
        if index is not None:
            if before:
                self._model.addRow(index)
            else:
                self._model.addRow(index + 1)

    def _createNewCanvas(self, editMode=False):
        [rows, cols] = self._model.size()

        if editMode:
            rows = rows + 1
            cols = cols + 1

        maxWidth = 1400
        maxHeight = 900

        wPixPerSquare = math.floor(maxWidth / cols)
        hPixPerSquare = math.floor(maxHeight / rows)
        self.pixPerTile = min(wPixPerSquare, hPixPerSquare)

        print("---> SIZE = " + str(cols*self.pixPerTile) + " x " +  str(rows*self.pixPerTile) + "; px= " + str(self.pixPerTile))

        self._canvas = QtGui.QPixmap(cols*self.pixPerTile, rows*self.pixPerTile)
        self._canvas.fill(QtGui.QColor('#ADD8E6')) # light blue

        # At least show light-blue filled rectangle in case there will be errors later
        self.label.setPixmap(self._canvas)

    def drawGrid(self, painter, cols, rows):
        pen = QtGui.QPen(QtGui.QColor('#000000'))  # black color
        pen.setStyle(QtCore.Qt.DashLine)
        pen.setWidth(1)
        painter.setPen(pen)

        for x in range(0, cols*self.pixPerTile, self.pixPerTile):
            painter.drawLine(x, 0, x, rows*self.pixPerTile)
        for y in range(0, rows*self.pixPerTile, self.pixPerTile):
            painter.drawLine(0, y, cols*self.pixPerTile, y)

    def redrawAll(self):
        [h, w] = self._model.size()
        self._createNewCanvas(editMode=True)

        painter = QtGui.QPainter(self._canvas)

        print("Drawing objects of level: " + str(self.selectionRange.zLevel))
        mapSquares = self._model.getAllSquares(self.selectionRange.zLevel)
        for squareModel in mapSquares:
            # Don not store. It's one-time object that just draws an object
            item = MapItemDrawer(squareModel, painter, self.pixPerTile, self._model._objCollection)

        # column delete buttons
        for x in range(w):
            item = DeleteButtonItem(painter, self.pixPerTile, x, h)
            # no need to store, will be garbage-collected

        # row delete buttons
        for y in range(h):
            item = DeleteButtonItem(painter, self.pixPerTile, w, y)
            # no need to store, will be garbage-collected
            
        self.drawGrid(painter, w, h)

        self.drawCurrentSelection(painter)

        painter.end()
        self.label.setPixmap(self._canvas)

    def drawCurrentSelection(self, painter):
        if self.selectionRange.startRow is not None and self.selectionRange.startCol is not None:
            # Draw a red rectangle around the selected square
            selectionPen = QtGui.QPen(QtGui.QColor('#FF0000'))  # red color
            selectionPen.setStyle(QtCore.Qt.DashLine)
            selectionPen.setWidth(4)
            painter.setPen(selectionPen)

            if self.selectionRange.endRow is not None and self.selectionRange.endCol is not None:
                startCol, startRow = self.selectionRange.startCol, self.selectionRange.startRow
                endCol, endRow = self.selectionRange.endCol, self.selectionRange.endRow
                x = startCol * self.pixPerTile
                y = startRow * self.pixPerTile
                w = (endCol - startCol + 1) * self.pixPerTile
                h = (endRow - startRow + 1) * self.pixPerTile
                painter.drawRect(x, y, w, h)
            else:
                painter.drawRect(self.selectionRange.startCol * self.pixPerTile, self.selectionRange.startRow * self.pixPerTile, self.pixPerTile, self.pixPerTile)
