# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import os
import json
import inspect

from modules.commonModels.MapModelGeneral import *

class GeneratorPluginBase:
    def __init__(self, mapModel):
        self.mapModel = mapModel
        self.generatedModel = 'Unknown' # or maybe None?
        self.pluginStaticSettings = {}
        self.schema = {}
        self.settings = {}
        self.childPluginClassName = self.__class__.__name__
        childPluginLocation = inspect.getfile(self.__class__)
        self.staticSettingsFileName = os.path.splitext(childPluginLocation)[0] + '.json'
        self.allPluginsSettingsFileName = 'generatorsSettings.json'
        self.loadPluginSettings()

    def loadPluginSettings(self):
        # Load the schema file specific to the plugin
        with open(self.staticSettingsFileName, 'r') as f:
            self.pluginStaticSettings = json.load(f)
            self.schema = self.pluginStaticSettings['schema']

        allSettings = self.loadAllPluginsSettings()

        # Merge the settings with the schema defaults
        pluginSettings = allSettings.get('plugins', {}).get(self.childPluginClassName, {})
        self.settings = self.applySchemaDefaults(pluginSettings)

    def savePluginSettings(self):
        allSettings = self.loadAllPluginsSettings()

        # Update the settings for this plugin
        allSettings['plugins'][self.childPluginClassName] = self.settings

        # Save the updated settings
        with open(self.allPluginsSettingsFileName, 'w') as f:
            json.dump(allSettings, f, indent=4)

        print("Settings saved")

    def loadAllPluginsSettings(self):
        # Load the global settings file (all plugins settings)
        if os.path.exists(self.allPluginsSettingsFileName):
            with open(self.allPluginsSettingsFileName, 'r') as f:
                allSettings = json.load(f)
        else:
            allSettings = {"plugins": {}}

        return allSettings

    def applySchemaDefaults(self, pluginSettings):
        updatedSettings = {}
        for key, value in self.schema.items():
            settingType = value.get('type')
            defaultValue = value.get('value')

            if key in pluginSettings:
                # If the setting exists in the loaded settings, use it
                updatedSettings[key] = pluginSettings[key]
            else:
                # Otherwise, use the default value from the schema
                updatedSettings[key] = defaultValue
        return updatedSettings
        
    def clear_generated(self):
        print("Clear generated " + str(self.generatedModel))
        res = self.mapModel.removeAllMapObjects(self.generatedModel)
        if (True == res):
            self.mapModel.updateEntireMap()
            print("Done")
        elif (False == res):
            print("Done (was empty)")
        else:
            self.mapModel.updateEntireMap()
            print("Done (smth wrong)")

    def generate(self):
        raise NotImplementedError("Each plugin must implement the run method.")
