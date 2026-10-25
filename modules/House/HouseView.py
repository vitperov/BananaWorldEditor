# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui
import numpy
import random

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from modules.MapWidget import *
from modules.PropertiesPanel import *
from modules.House.HouseToolbar import *

class HouseView(QWidget):
    """House Editor View Widget."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('BananaWorldEditor — House Editor')

        self._createWidgets()

        self.setLayout(self._createLayout())

    def _createWidgets(self):
        self.mapWidget = MapWidget()
        category = 'indoor'
        self.propPanel = PropertiesPanel(category)
        self.actionsPanel = HouseToolbar()

    def _createLayout(self):
        layout = QVBoxLayout()

        layout.addWidget(self.actionsPanel)
        mapLayout = QHBoxLayout()
        layout.addLayout(mapLayout)

        mapLayout.addWidget(self.mapWidget)
        mapLayout.addWidget(self.propPanel)

        return layout
