# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#import PyQt5
    
import sys
from functools import partial
import datetime

from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui
import numpy


from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

class TerrainMapController:
    def __init__(self, view, model):
        self._view = view
        self._model = model

        self._provideModel()
        self._connectSignals()
        self._startActions()

    def _provideModel(self):
        self._view.mapWidget.setModel(self._model.map)
        self._view.propPanel.setModel(self._model.map)
        self._view.actionsPanel.openMap.connect(self._model.map.openMap)
        self._view.actionsPanel.saveMap.connect(self._model.map.saveMap)
        self._view.actionsPanel.mapSettings.connect(self._onSettingsClick)
        self._view.actionsPanel.refreshMap.connect(self._view.mapWidget.redrawAll)

    def _connectSignals(self):
        self._model.map.updatedEntireMap.connect(self._view.mapWidget.redrawAll)
        self._model.map.currentFileChanged.connect(self._view.actionsPanel.setCurrentPath)
        self._view.mapWidget.selectionChanged.connect(self._view.propPanel.onSquaresSelected)

    def _startActions(self):
        self._view.generatorsPanel.populateGenerators(self._model.generators.generators)

    def _onSettingsClick(self):
        TerrainGeneratorSettingsDlg.runDlg("Terrain generator settings", \
            self._model.generators.generators[1][2].settings, self._view) # EverythingGenerator was renamed to LandLotContentGenerator
