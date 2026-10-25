# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QPushButton, QShortcut
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon, QKeySequence

from modules.ApplicationSettings.ApplicationSettingsModel import ApplicationSettingsModel
from modules.commonModels.MapFileDialogs import MapFileDialogs

class TerrainToolbar(QWidget):
    mapSettings  = pyqtSignal()
    openMap      = pyqtSignal(str)
    saveMap      = pyqtSignal(str)
    refreshMap   = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)

        self._fileDialogs = MapFileDialogs(ApplicationSettingsModel.getTerrainMapsDir, 'output/terrain')
        # Path of the map currently open, mirrored from the model so Save can
        # write straight to it. '' until a map has been opened or saved.
        self._currentPath = ''

        self._settingsBtn   = QPushButton("Generator settings")
        self._openBtn       = QPushButton("Open")
        self._saveBtn       = QPushButton("Save")
        self._saveAsBtn     = QPushButton("Save As")
        self._refreshButton = QPushButton("Refresh", self)

        self._openBtn.setIcon(QIcon.fromTheme("document-open"))
        self._saveBtn.setIcon(QIcon.fromTheme("document-save"))
        self._saveAsBtn.setIcon(QIcon.fromTheme("document-save-as"))
        self._refreshButton.setIcon(QIcon.fromTheme("view-refresh"))

        self._layout.addWidget(self._settingsBtn)
        self._layout.addWidget(self._openBtn)
        self._layout.addWidget(self._saveBtn)
        self._layout.addWidget(self._saveAsBtn)
        self._layout.addWidget(self._refreshButton)

        self._layout.addStretch()

        self._settingsBtn.clicked.connect(self._settingsDlg)
        self._openBtn.clicked.connect(self._openFile)
        self._saveBtn.clicked.connect(self._saveFile)
        self._saveAsBtn.clicked.connect(self._saveFileAs)
        self._refreshButton.clicked.connect(self._refreshAction)

        QShortcut(QKeySequence.Open, self, self._openFile)
        QShortcut(QKeySequence.Save, self, self._saveFile)
        QShortcut(QKeySequence.SaveAs, self, self._saveFileAs)

    def setCurrentPath(self, path):
        """Follow the model's open file, so Save knows where to write."""
        self._currentPath = path

    def _settingsDlg(self):
        self.mapSettings.emit()

    def _saveFile(self):
        # Save over the open file without a dialog; fall back to asking when
        # the map has no file yet.
        if self._currentPath:
            self.saveMap.emit(self._currentPath)
        else:
            self._saveFileAs()

    def _saveFileAs(self):
        name = self._fileDialogs.promptSave(self, self._currentPath)
        if name:
            self.saveMap.emit(name)

    def _openFile(self):
        name = self._fileDialogs.promptOpen(self, self._currentPath)
        if name:
            self.openMap.emit(name)

    def _refreshAction(self):
        self.refreshMap.emit()
