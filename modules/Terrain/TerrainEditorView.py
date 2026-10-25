# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui
import numpy
import random

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from modules.MapWidget import *
from modules.Terrain.TerrainToolbar import *
from modules.PropertiesPanel import *
from modules.GeneratorsPanel import *

class TerrainEditorView(QWidget):
    """Terrain Editor View Widget."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('BananaWorldEditor — Map Generator')

        self._createWidgets()

        self.setLayout(self._createLayout())

    def _createWidgets(self):
        self.actionsPanel = TerrainToolbar()
        self.mapWidget = MapWidget()
        category = 'outdoor'
        self.propPanel = PropertiesPanel(category)
        self.generatorsPanel = GeneratorsPanel()

    def _createLayout(self):
        layout = QHBoxLayout()
        mapLayout = QVBoxLayout()
        layout.addLayout(mapLayout)
        
        mapLayout.addWidget(self.actionsPanel)
        mapLayout.addWidget(self.mapWidget)
        mapLayout.addStretch()
        
        rightLayout = QVBoxLayout()
        rightLayout.addWidget(self.generatorsPanel)
        rightLayout.addWidget(self.propPanel)
        
        layout.addStretch()
        layout.addLayout(rightLayout)

        return layout
