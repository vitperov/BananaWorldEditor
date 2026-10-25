# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import os

from PyQt5.QtWidgets import QFileDialog

from modules.ApplicationSettings.ApplicationSettingsModel import ApplicationSettingsModel


class MapFileDialogs:
    """Open/Save dialogs for map files, rooted at a directory from Application
    Settings.

    Each editor kind keeps its maps somewhere different (Terrain and House sit
    in unrelated folders in the game project), so one instance is built per
    editor with the accessor for its own setting.

    The setting is re-read for every dialog, so changing it in Settings takes
    effect without restarting the editor. An unset or missing directory falls
    back to the editor-local scratch folder, which keeps the editor usable
    without a game project checked out.
    """

    def __init__(self, dirFromSettings, fallbackDir):
        # dirFromSettings: ApplicationSettingsModel -> str, e.g.
        # ApplicationSettingsModel.getTerrainMapsDir
        self._dirFromSettings = dirFromSettings
        self._fallbackDir = fallbackDir

    def configuredDir(self):
        configured = self._dirFromSettings(ApplicationSettingsModel())
        if configured and os.path.isdir(configured):
            return configured
        return self._fallbackDir

    def _startPath(self, currentPath):
        # Once a map is open, offer its own location: the user may have
        # navigated away from the configured root deliberately for this map.
        if currentPath:
            return currentPath
        return self.configuredDir()

    def promptOpen(self, parent, currentPath=None):
        """Ask for a map to open. Returns the path, or '' if cancelled."""
        name, _ = QFileDialog.getOpenFileName(parent, 'Open File', self._startPath(currentPath), filter='*.json')
        return name

    def promptSave(self, parent, currentPath=None):
        """Ask where to save a map. Returns the path, or '' if cancelled."""
        name, _ = QFileDialog.getSaveFileName(parent, 'Save File', self._startPath(currentPath), filter='*.json')
        return name
