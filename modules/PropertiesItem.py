# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from modules.commonModels.SelectionRange import *
from PyQt5 import QtWidgets, QtGui
from pyqtgraph.Qt import QtCore

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from functools import partial
from modules.SimpleSquareItem import SimpleSquareItem
from modules.ChooseRotationDlg import ChooseRotationDlg
from modules.ChooseModelDlg import ChooseModelDlg
from modules.AdditionalPropertiesDlg import AdditionalPropertiesDlg

class PropertiesItem(QWidget):
    updateAllProperties = pyqtSignal()  # Signal to notify when properties are updated

    def __init__(self, objModel, objCollection, mapModel, selectionRange, category, tilesize=64, parent=None):
        super(PropertiesItem, self).__init__(parent)  # Initialize QWidget directly
        self._model = objModel
        self._mapModel = mapModel
        self._category = category
        self._selectionRange = selectionRange
        self._objCollection = objCollection
        
        multi_select = not (
            self._selectionRange.startCol == self._selectionRange.endCol and 
            self._selectionRange.startRow == self._selectionRange.endRow
        )

        sqType = self._model.getProperty('model')
        if multi_select:
            sqType += " (multiple squares)"

        # Create a layout for the widget
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        # Set up the group box
        groupBox = QGroupBox(sqType, self)
        groupBoxLayout = QHBoxLayout()  # Change to QHBoxLayout for horizontal arrangement
        groupBoxLayout.setSpacing(0)
        groupBoxLayout.setContentsMargins(0, 0, 0, 0)
        groupBox.setLayout(groupBoxLayout)
        layout.addWidget(groupBox)
        
        # Change groupbox background if multiple squares are selected
        if multi_select:
            groupBox.setStyleSheet("background-color: #A5CEC0")

        # Add SimpleSquareItem
        self.modelPicture = SimpleSquareItem(objModel, objCollection, tilesize, multi_select)
        groupBoxLayout.addWidget(self.modelPicture)

        # Create a grid layout for control buttons
        buttonLayout = QGridLayout()
        buttonLayout.setSpacing(0)
        buttonLayout.setContentsMargins(0, 0, 0, 0)
        groupBoxLayout.addLayout(buttonLayout)
        
        # Model Button
        modelBtn = QPushButton()
        modelBtn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        modelBtn.clicked.connect(self.showChooseModelDlg)
        buttonLayout.addWidget(modelBtn, 0, 0)

        # Rotation Button
        rotationBtn = QPushButton()
        rotationBtn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        rotationBtn.clicked.connect(self.showChooseRotationDlg)
        buttonLayout.addWidget(rotationBtn, 1, 0)

        # Remove Button
        removeBtn = QPushButton()
        removeBtn.setIcon(self.style().standardIcon(QStyle.SP_DialogCancelButton))
        buttonLayout.addWidget(removeBtn, 2, 0)
        removeBtn.clicked.connect(self.removeObject)

        # Move Up Button
        moveUpBtn = QPushButton()
        moveUpBtn.setIcon(self.style().standardIcon(QStyle.SP_ArrowUp))
        moveUpBtn.clicked.connect(partial(self.moveObject, 0, -1))
        buttonLayout.addWidget(moveUpBtn, 0, 1)

        # Move Down Button
        moveDownBtn = QPushButton()
        moveDownBtn.setIcon(self.style().standardIcon(QStyle.SP_ArrowDown))
        moveDownBtn.clicked.connect(partial(self.moveObject, 0, 1))
        buttonLayout.addWidget(moveDownBtn, 1, 1)

        # Move Left Button
        moveLeftBtn = QPushButton()
        moveLeftBtn.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        moveLeftBtn.clicked.connect(partial(self.moveObject, -1, 0))
        buttonLayout.addWidget(moveLeftBtn, 2, 1)

        # Move Right Button
        moveRightBtn = QPushButton()
        moveRightBtn.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        moveRightBtn.clicked.connect(partial(self.moveObject, 1, 0))
        buttonLayout.addWidget(moveRightBtn, 1, 2)

        # Show Properties Button
        additionalProps = self._objCollection.getAdditionalProperties(self._model.getProperty('model'))
        if additionalProps:
            showPropertiesBtn = QPushButton()
            showPropertiesBtn.setIcon(self.style().standardIcon(QStyle.SP_FileDialogListView))
            showPropertiesBtn.clicked.connect(self.showProperties)
            buttonLayout.addWidget(showPropertiesBtn, 0, 2)

    def _is_single_square_selection(self):
        return (self._selectionRange.startCol == self._selectionRange.endCol and
                self._selectionRange.startRow == self._selectionRange.endRow)

    def moveObject(self, x_offset, y_offset):
        self._model.x += x_offset
        self._model.y += y_offset
        self.updateAllProperties.emit()

        # Update the model in the map and redraw
        self._mapModel.updateEntireMap()

    def showChooseRotationDlg(self):
        dlg = ChooseRotationDlg(self._model, self._mapModel._objCollection, 64)
        if dlg.exec_() == QDialog.Accepted:
            chosenRotation = dlg.selectedRotation
            if chosenRotation is not None:
                if self._is_single_square_selection():
                    # Apply rotation only to the specific object instance
                    self._model.setProperty('rotation', str(chosenRotation))
                    self._mapModel.updateEntireMap()
                    self.modelPicture.updatePixmap()
                else:
                    # Apply rotation to all objects of this type in the selection area
                    self._mapModel.setGroupProperty(self._selectionRange, self._model.getProperty('model'), 'rotation', str(chosenRotation))
                    self._mapModel.updateEntireMap()
                    self.modelPicture.updatePixmap()

    def showChooseModelDlg(self):
        dlg = ChooseModelDlg(self._mapModel._objCollection, self._category, 64)
        if dlg.exec_() == QDialog.Accepted:
            chosenModel = dlg.selectedModel
            if chosenModel is not None:
                if self._is_single_square_selection():
                    # Change model only for the specific object instance
                    self._model.setProperty('model', chosenModel)
                    self._mapModel.updateModelSize(self._model)
                    self._mapModel.updateEntireMap()
                    self.modelPicture.updatePixmap()
                else:
                    # Change model for all objects of the old type in the selection area
                    self._mapModel.setGroupProperty(self._selectionRange, self._model.getProperty('model'), 'model', chosenModel)
                    self._mapModel.updateEntireMap()
                    self.modelPicture.updatePixmap()

    def removeObject(self):
        if self._is_single_square_selection():
            # Remove only the specific object instance
            self._mapModel.deleteSquareById(self._model.id)
        else:
            # Remove all objects of this type in the selection area
            model_type = self._model.getProperty('model')
            self._mapModel.deleteObjectsInSelection(self._selectionRange, model_type)
        self.updateAllProperties.emit()

    def showProperties(self):
        modelType = self._model.getProperty('model')
        dlg = AdditionalPropertiesDlg(self._objCollection, self._mapModel, self._mapModel._texturesCollection, self._mapModel._lootContainersCollection, self._selectionRange, modelType, self)
        if dlg.exec_() == QDialog.Accepted:
            print("Additional properties accepted")
