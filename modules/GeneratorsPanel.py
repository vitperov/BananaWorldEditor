# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5 import QtWidgets
from pyqtgraph.Qt import QtCore, QtGui
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from modules.commonModels.ThemeIcons import themedIcon
from PyQt5.QtCore import pyqtSignal, pyqtSlot

from functools import partial

class GeneratorSettings(QWidget):
    def __init__(self, model):
        QWidget.__init__(self)
        self.model = model
        self.controls = {}
        self.initGui()

    def initGui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        for key, info in self.model.schema.items():
            controlLayout = QHBoxLayout()
            label = QLabel(key)
            controlLayout.addWidget(label)

            settingType = info['type']
            settingValue = self.model.settings[key]
            #print("    " + key + "->" + str(settingValue))
            
            def parseBool(var):
                if var.lower() == "false":
                    return False
                elif var.lower() == "true":
                    return True
                else:
                    raise Exception("Unsupported boolean value: " + var)
            
            if settingType == 'str':
                control = QLineEdit()
                control.setText(settingValue)
            elif settingType == 'int':
                control = QSpinBox()
                control.setValue(int(settingValue))
            elif settingType == 'float':
                control = QDoubleSpinBox()
                control.setDecimals(2)
                control.setRange(-1e6, 1e6)  # Set an appropriate range for your needs
                control.setValue(float(settingValue))
            elif settingType == 'bool':
                control = QCheckBox()
                control.setChecked(parseBool(settingValue))
            else:
                raise Exception("Unsupported schema type: " + settingType)
            
            controlLayout.addWidget(control)
            layout.addLayout(controlLayout)
            self.controls[key] = control

        applyButton = QPushButton("Save & Apply")
        applyButton.clicked.connect(self.applySettings)
        layout.addWidget(applyButton)

    def applySettings(self):
        for key, control in self.controls.items():
            if isinstance(control, QLineEdit):
                self.model.settings[key] = control.text()
            elif isinstance(control, QSpinBox):
                self.model.settings[key] = str(control.value())
            elif isinstance(control, QDoubleSpinBox):
                self.model.settings[key] = str(control.value())
            elif isinstance(control, QCheckBox):
                self.model.settings[key] = str(control.isChecked())

        self.model.savePluginSettings()

class GeneratorItem(QGroupBox):
    def __init__(self, name, model, parent=None):
        super(GeneratorItem, self).__init__(name, parent)
        self.name = name
        self.model = model
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        firstRowLayout = QHBoxLayout()
        self.toggleButton = QToolButton()
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(False)
        self._setToggleIcon(False)
        self.toggleButton.clicked.connect(self.toggleSettings)

        firstRowLayout.addWidget(self.toggleButton)
        layout.addLayout(firstRowLayout)
        
        generateBtn = QPushButton("Generate")
        firstRowLayout.addWidget(generateBtn)
        generateBtn.clicked.connect(model.generate)
        
        clearBtn = QPushButton("Clear generated")
        firstRowLayout.addWidget(clearBtn)
        clearBtn.clicked.connect(model.clear_generated)

        self.settingsWg = GeneratorSettings(model)
        layout.addWidget(self.settingsWg)
        self.settingsWg.hide()

    # Theme icons depend on a freedesktop icon theme; on bare systems fall
    # back to Qt's built-in arrows so the expand/collapse state still reads.
    def _setToggleIcon(self, expanded):
        themeName = "list-remove" if expanded else "list-add"
        fallback = QStyle.SP_ArrowUp if expanded else QStyle.SP_ArrowDown
        self.toggleButton.setIcon(themedIcon(self, themeName, fallback))

    def toggleSettings(self):
        if self.toggleButton.isChecked():
            self.settingsWg.show()
            self._setToggleIcon(True)  # Show minus icon when expanded
        else:
            self.settingsWg.hide()
            self._setToggleIcon(False)  # Show plus icon when collapsed

class GeneratorsPanel(QWidget):
    generateSignal = pyqtSignal(str, dict)
    def __init__(self):
        QWidget.__init__(self)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
    
    def populateGenerators(self, generatorsModels):
        for name, order, model in generatorsModels:
            genItem = GeneratorItem(name, model)
            self.layout.addWidget(genItem)
