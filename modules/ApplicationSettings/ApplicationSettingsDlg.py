# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog
from PyQt5.QtCore import Qt
from modules.ApplicationSettings.ApplicationSettingsModel import ApplicationSettingsModel

class ApplicationSettingsDlg(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Application Settings")
        self.setModal(True)
        
        # Initialize settings model within the dialog
        self.settingsModel = ApplicationSettingsModel()

        # Layout for the dialog
        layout = QVBoxLayout()

        # Input for additionalMapObjectsDir with directory chooser button
        self.mapObjectsDirLabel = QLabel("Additional Map Objects Directory:")
        mapObjectsDirLayout = QHBoxLayout()
        self.mapObjectsDirInput = QLineEdit()
        self.mapObjectsDirInput.setText(self.settingsModel.getAdditionalMapObjectsDir())  # Load existing value
        self.mapObjectsDirButton = QPushButton("Browse")
        self.mapObjectsDirButton.clicked.connect(self.chooseMapObjectsDir)  # Connect to directory chooser
        mapObjectsDirLayout.addWidget(self.mapObjectsDirInput)
        mapObjectsDirLayout.addWidget(self.mapObjectsDirButton)
        layout.addWidget(self.mapObjectsDirLabel)
        layout.addLayout(mapObjectsDirLayout)

        # Input for additionalGeneratorsDir with directory chooser button
        self.generatorsDirLabel = QLabel("Additional Generators Directory:")
        generatorsDirLayout = QHBoxLayout()
        self.generatorsDirInput = QLineEdit()
        self.generatorsDirInput.setText(self.settingsModel.getAdditionalGeneratorsDir())  # Load existing value
        self.generatorsDirButton = QPushButton("Browse")
        self.generatorsDirButton.clicked.connect(self.chooseGeneratorsDir)  # Connect to directory chooser
        generatorsDirLayout.addWidget(self.generatorsDirInput)
        generatorsDirLayout.addWidget(self.generatorsDirButton)
        layout.addWidget(self.generatorsDirLabel)
        layout.addLayout(generatorsDirLayout)

        # Input for additionalTexturesDir with directory chooser button
        self.texturesDirLabel = QLabel("Additional Textures Directory:")
        texturesDirLayout = QHBoxLayout()
        self.texturesDirInput = QLineEdit()
        self.texturesDirInput.setText(self.settingsModel.getAdditionalTexturesDir())  # Load existing value
        self.texturesDirButton = QPushButton("Browse")
        self.texturesDirButton.clicked.connect(self.chooseTexturesDir)  # Connect to directory chooser
        texturesDirLayout.addWidget(self.texturesDirInput)
        texturesDirLayout.addWidget(self.texturesDirButton)
        layout.addWidget(self.texturesDirLabel)
        layout.addLayout(texturesDirLayout)

        # Input for terrainMapsDir with directory chooser button
        self.terrainMapsDirLabel = QLabel("Terrain Maps Directory:")
        terrainMapsDirLayout = QHBoxLayout()
        self.terrainMapsDirInput = QLineEdit()
        self.terrainMapsDirInput.setText(self.settingsModel.getTerrainMapsDir())  # Load existing value
        self.terrainMapsDirButton = QPushButton("Browse")
        self.terrainMapsDirButton.clicked.connect(self.chooseTerrainMapsDir)  # Connect to directory chooser
        terrainMapsDirLayout.addWidget(self.terrainMapsDirInput)
        terrainMapsDirLayout.addWidget(self.terrainMapsDirButton)
        layout.addWidget(self.terrainMapsDirLabel)
        layout.addLayout(terrainMapsDirLayout)

        # Input for houseMapsDir with directory chooser button
        self.houseMapsDirLabel = QLabel("House Maps Directory:")
        houseMapsDirLayout = QHBoxLayout()
        self.houseMapsDirInput = QLineEdit()
        self.houseMapsDirInput.setText(self.settingsModel.getHouseMapsDir())  # Load existing value
        self.houseMapsDirButton = QPushButton("Browse")
        self.houseMapsDirButton.clicked.connect(self.chooseHouseMapsDir)  # Connect to directory chooser
        houseMapsDirLayout.addWidget(self.houseMapsDirInput)
        houseMapsDirLayout.addWidget(self.houseMapsDirButton)
        layout.addWidget(self.houseMapsDirLabel)
        layout.addLayout(houseMapsDirLayout)

        # Save button layout
        buttonLayout = QHBoxLayout()
        buttonLayout.addStretch()  # Push button to the right
        self.saveButton = QPushButton("Save")
        self.saveButton.clicked.connect(self.saveSettings)  # Connect to save action
        buttonLayout.addWidget(self.saveButton)
        layout.addLayout(buttonLayout)

        self.setLayout(layout)

    def chooseMapObjectsDir(self):
        # Open directory chooser dialog for additionalMapObjectsDir
        directory = QFileDialog.getExistingDirectory(self, "Select Additional Map Objects Directory")
        if directory:
            self.mapObjectsDirInput.setText(directory)

    def chooseGeneratorsDir(self):
        # Open directory chooser dialog for additionalGeneratorsDir
        directory = QFileDialog.getExistingDirectory(self, "Select Additional Generators Directory")
        if directory:
            self.generatorsDirInput.setText(directory)

    def chooseTexturesDir(self):
        # Open directory chooser dialog for additionalTexturesDir
        directory = QFileDialog.getExistingDirectory(self, "Select Additional Textures Directory")
        if directory:
            self.texturesDirInput.setText(directory)

    def chooseTerrainMapsDir(self):
        # Open directory chooser dialog for terrainMapsDir
        directory = QFileDialog.getExistingDirectory(self, "Select Terrain Maps Directory", self.terrainMapsDirInput.text())
        if directory:
            self.terrainMapsDirInput.setText(directory)

    def chooseHouseMapsDir(self):
        # Open directory chooser dialog for houseMapsDir
        directory = QFileDialog.getExistingDirectory(self, "Select House Maps Directory", self.houseMapsDirInput.text())
        if directory:
            self.houseMapsDirInput.setText(directory)

    def saveSettings(self):
        # Update settings model with new values
        self.settingsModel.setAdditionalMapObjectsDir(self.mapObjectsDirInput.text())
        self.settingsModel.setAdditionalGeneratorsDir(self.generatorsDirInput.text())
        self.settingsModel.setAdditionalTexturesDir(self.texturesDirInput.text())
        self.settingsModel.setTerrainMapsDir(self.terrainMapsDirInput.text())
        self.settingsModel.setHouseMapsDir(self.houseMapsDirInput.text())
        self.accept()  # Close dialog after saving
