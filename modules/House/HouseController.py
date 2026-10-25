# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import sys
from functools import partial
import datetime

from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui
import numpy


from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from modules.commonModels.EditorHelper import EditorHelper

class HouseController:
    def __init__(self, view, houseModel):
        self._view = view
        self._houseModel = houseModel
        self._editorHelper = EditorHelper(self._houseModel)

        self._provideModel()
        self._connectSignals()

    def _provideModel(self):
        self._view.mapWidget.setModel(self._houseModel)
        self._view.propPanel.setModel(self._houseModel)

    def _connectSignals(self):
        self._view.mapWidget.selectionChanged.connect(self._view.propPanel.onSquaresSelected)
        self._view.actionsPanel.newMap.connect(self._houseModel.newMap)
        self._view.actionsPanel.openMap.connect(self._houseModel.openMap)
        self._view.actionsPanel.saveMap.connect(self._houseModel.saveMap)
        self._view.actionsPanel.addColumn.connect(self._view.mapWidget.addColumn)
        self._view.actionsPanel.addRow.connect(self._view.mapWidget.addRow)
        self._view.actionsPanel.zLevelChanged.connect(self._setZLevel)
        self._view.actionsPanel.floorHeightChanged.connect(self._setFloorHeight)
        self._view.actionsPanel.generateWallFrame.connect(self._generateWallFrame)
        self._view.actionsPanel.generateRoofFrame.connect(self._generateRoofFrame)
        self._view.actionsPanel.generateRoofFrameHalf.connect(self._generateRoofFrameHalf)

        self._houseModel.updatedEntireMap.connect(self._view.mapWidget.redrawAll)
        self._houseModel.updatedEntireMap.connect(self._syncFloorHeight)
        self._houseModel.currentFileChanged.connect(self._view.actionsPanel.setCurrentPath)
        self._view.propPanel.updatedEntireMap.connect(self._view.mapWidget.redrawAll)

        self._view.mapWidget.deleteRow.connect(self._houseModel.deleteRow)
        self._view.mapWidget.deleteColumn.connect(self._houseModel.deleteColumn)

    def _setZLevel(self, zLevel):
        self._view.mapWidget.selectionRange.zLevel = zLevel
        self._view.mapWidget.redrawAll()

    def _setFloorHeight(self, value):
        self._houseModel.floorHeight = value

    def _syncFloorHeight(self):
        # Keep the toolbar spin box in step with the model (e.g. after openMap
        # restores floorHeight from the file).
        self._view.actionsPanel.setFloorHeight(self._houseModel.floorHeight)

    def _generateWallFrame(self):
        selection = self._view.mapWidget.selectionRange
        self._editorHelper.generateWallFrame(selection)
        self._view.mapWidget.redrawAll()

    def _generateRoofFrame(self):
        selection = self._view.mapWidget.selectionRange
        self._editorHelper.generateRoofFrame(selection)
        self._view.mapWidget.redrawAll()

    def _generateRoofFrameHalf(self):
        selection = self._view.mapWidget.selectionRange
        self._editorHelper.generateRoofFrameHalf(selection)
        self._view.mapWidget.redrawAll()
