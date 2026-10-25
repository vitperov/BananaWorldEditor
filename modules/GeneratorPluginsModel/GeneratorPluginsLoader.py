# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import importlib
import os
import pkgutil
import warnings

from modules.GeneratorPluginsModel.GeneratorPluginBase import *

class GeneratorPluginsLoader:
    def __init__(self, mapModel):
        self.generators = []
        self.mapModel = mapModel

    def loadPluginsFrom(self, directory):
        modulePath = directory.replace(os.sep, '.')
        while modulePath.startswith('.'):
            modulePath = modulePath[1:]

        for _, name, is_pkg in pkgutil.iter_modules([directory]):
            fullModuleName = f'{modulePath}.{name}'

            if not is_pkg:
                print("Importing: " + fullModuleName)
                module = importlib.import_module(fullModuleName)
                foundPlugin = False
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and issubclass(obj, GeneratorPluginBase) and obj is not GeneratorPluginBase:
                        pluginInstance = obj(self.mapModel)
                        order = float(pluginInstance.pluginStaticSettings.get('order', float('inf')))
                        self.generators.append((name, order, pluginInstance))
                        foundPlugin = True
                if not foundPlugin:
                    warnings.warn(f"Module '{fullModuleName}' does not contain any class derived from GeneratorPluginBase")
            else:
                print("Loading packages is not implemented: " + fullModuleName)

        # Sort the generators by the order value
        self.generators.sort(key=lambda x: x[1])

    def printLoaded(self):
        for name, order, plugin in self.generators:
            print(f"{name} (order: {order}):")
