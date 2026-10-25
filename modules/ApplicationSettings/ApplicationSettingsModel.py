# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import json
import os

class ApplicationSettingsModel:
    def __init__(self, settings_file="settings/application.json"):
        self.settings_file = settings_file
        self.settings = {}

        # Load settings from file if it exists
        if os.path.exists(self.settings_file):
            with open(self.settings_file, "r") as f:
                try:
                    self.settings = json.load(f)
                except json.JSONDecodeError:
                    print(f"Error: Could not decode JSON from {self.settings_file}")
                    self.settings = {}
        else:
            print(f"Settings file {self.settings_file} not found. Using default settings.")

    # Getter and Setter for additionalMapObjectsDir
    def getAdditionalMapObjectsDir(self):
        return self.settings.get("additionalMapObjectsDir", "")

    def setAdditionalMapObjectsDir(self, value):
        self.settings["additionalMapObjectsDir"] = value
        self._saveSettings()

    # Getter and Setter for additionalGeneratorsDir
    def getAdditionalGeneratorsDir(self):
        return self.settings.get("additionalGeneratorsDir", "")

    def setAdditionalGeneratorsDir(self, value):
        self.settings["additionalGeneratorsDir"] = value
        self._saveSettings()

    # Getter and Setter for additionalTexturesDir
    def getAdditionalTexturesDir(self):
        return self.settings.get("additionalTexturesDir", "")

    def setAdditionalTexturesDir(self, value):
        self.settings["additionalTexturesDir"] = value
        self._saveSettings()

    # Directory the Terrain editor opens and saves maps in. Points at the game
    # project's own map folder (e.g. <unity>/Assets/Resources/Maps/Terrain) so
    # maps are edited in place instead of copied through output/. Empty falls
    # back to output/terrain, keeping the editor usable without a game checkout.
    def getTerrainMapsDir(self):
        return self.settings.get("terrainMapsDir", "")

    def setTerrainMapsDir(self, value):
        self.settings["terrainMapsDir"] = value
        self._saveSettings()

    # Same for the House editor (e.g. <unity>/Assets/Resources/Maps/House/json).
    # Kept independent of terrainMapsDir: the two sit at different depths, and
    # deriving one from the other would tie the editor to one project's layout.
    def getHouseMapsDir(self):
        return self.settings.get("houseMapsDir", "")

    def setHouseMapsDir(self, value):
        self.settings["houseMapsDir"] = value
        self._saveSettings()

    def _saveSettings(self):
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.settings_file), exist_ok=True)
        # Write updated settings to file
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)
