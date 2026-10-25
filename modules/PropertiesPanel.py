# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.commonModels.SelectionRange import *
from PyQt5 import QtWidgets, QtGui
from pyqtgraph.Qt import QtCore

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from functools import partial
from modules.SimpleSquareItem import SimpleSquareItem
from modules.ChooseRotationDlg import ChooseRotationDlg
from modules.ChooseModelDlg import ChooseModelDlg
from modules.AdditionalPropertiesDlg import AdditionalPropertiesDlg
from modules.PropertiesItem import PropertiesItem

class PropertiesPanel(QWidget):
    updatedEntireMap = pyqtSignal()
    def __init__(self, category):
        QWidget.__init__(self)

        self.selectionRange = None
        self._category = category

        layout = QVBoxLayout()
        self.setLayout(layout)

        addBtn = QPushButton()
        addBtn.setIcon(QtGui.QIcon('resources/greenPlus.png'))
        layout.addWidget(addBtn)
        addBtn.clicked.connect(self.addObject)

        self.coordinatesLbl = QLabel("X: ? Y: ?")
        layout.addWidget(self.coordinatesLbl)

        self.properties = QGridLayout()
        self.properties.setSpacing(0)
        layout.addLayout(self.properties)

        layout.addStretch()  # Add vertical spacer at the end

    def setModel(self, model):
        self.mapModel = model

    def onSquaresSelected(self, selectionRange):
        self.selectionRange = selectionRange

        startCol = selectionRange.startCol
        startRow = selectionRange.startRow
        endCol = selectionRange.endCol
        endRow = selectionRange.endRow
        zLevel = selectionRange.zLevel

        for i in reversed(range(self.properties.count())):
            self.properties.itemAt(i).widget().setParent(None)

        if startCol == endCol and startRow == startRow:
            items = self.mapModel.getSquareItems(startCol, startRow, zLevel)
            self.coordinatesLbl.setText("X: " + str(startCol) + " Y: " + str(startRow) + " Zlevel: " + str(zLevel))
        else:
            items = self.mapModel.getAreaSquareUniqueItems(selectionRange)
            width = abs(endCol - startCol) + 1
            height = abs(endRow - startRow) + 1
            totalItems = width * height
            self.coordinatesLbl.setText(f"{totalItems} squares selected")
        
        MAX_ROWS = 9
        for index, itemModel in enumerate(items):
            itemWg = PropertiesItem(itemModel, self.mapModel._objCollection, self.mapModel, self.selectionRange, self._category)
            row = index % MAX_ROWS
            col = index // MAX_ROWS
            self.properties.addWidget(itemWg, row, col)

    def addObject(self):
        if self.selectionRange is not None:
            self.mapModel.createObjectsInSelection(self.selectionRange)
            self.onSquaresSelected(self.selectionRange)
            self.updatedEntireMap.emit()

    def update(self):
        if self.selectionRange:
            self.onSquaresSelected(self.selectionRange)
