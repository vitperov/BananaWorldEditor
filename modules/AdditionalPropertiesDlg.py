# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget, QHBoxLayout, QPushButton, QCheckBox
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import pyqtSignal
from modules.commonModels.ObjectsCollection import ObjectsCollection
from modules.commonModels.MapModelGeneral import MapObjectModelGeneral
from modules.ChooseTextureDlg import ChooseTextureDlg
import os


class UnknownTypeWidget(QWidget):
    def __init__(self, name, type, value, parent=None):
        super(UnknownTypeWidget, self).__init__(parent)
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        name_label = QLabel(f"Name: {name}")
        type_label = QLabel(f"Type: {type}")
        value_label = QLabel(f"Value: {value}")
        
        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(value_label)


class TextureTypeWidget(QWidget):
    ICON_SIZE = 48

    def __init__(self, name, type, value, texturesCollection, mapModel, selectionRange, modelType, parent=None):
        super(TextureTypeWidget, self).__init__(parent)
        layout = QHBoxLayout()
        self.setLayout(layout)
        
        self.name = name
        self.type = type
        self.value = value
        self.texturesCollection = texturesCollection
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")
        
        layout.addWidget(name_label)
        layout.addWidget(type_label)
        
        iconPath = self.texturesCollection.getIcon(self.value)
        self.icon_button = QPushButton()
        if iconPath and os.path.exists(iconPath):
            pixmap = QtGui.QPixmap(iconPath)
        else:
            pixmap = self.style().standardIcon(QtWidgets.QStyle.SP_DialogCancelButton).pixmap(self.ICON_SIZE, self.ICON_SIZE)
        pixmap = pixmap.scaled(self.ICON_SIZE, self.ICON_SIZE)
        self.icon_button.setIcon(QtGui.QIcon(pixmap))
        self.icon_button.setIconSize(QtCore.QSize(self.ICON_SIZE, self.ICON_SIZE))
        layout.addWidget(self.icon_button)

        self.icon_button.clicked.connect(self.on_icon_clicked)

    def on_icon_clicked(self):
        dlg = ChooseTextureDlg(self.texturesCollection, self)
        if dlg.exec_() == QDialog.Accepted:
            selected_texture = dlg.selectedTexture
            if selected_texture:
                self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: selected_texture})
                self.value = selected_texture
                self.update_icon()

    def update_icon(self):
        iconPath = self.texturesCollection.getIcon(self.value)
        if iconPath and os.path.exists(iconPath):
            pixmap = QtGui.QPixmap(iconPath)
        else:
            pixmap = self.style().standardIcon(QtWidgets.QStyle.SP_DialogCancelButton).pixmap(self.ICON_SIZE, self.ICON_SIZE)
        pixmap = pixmap.scaled(self.ICON_SIZE, self.ICON_SIZE)
        self.icon_button.setIcon(QtGui.QIcon(pixmap))


class StringTypeWidget(QWidget):
    def __init__(self, name, type, value, mapModel, selectionRange, modelType, parent=None):
        super(StringTypeWidget, self).__init__(parent)
        self.name = name
        self.type = type
        self.value = value if value != "Not Set" else ""
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        layout = QHBoxLayout()
        self.setLayout(layout)

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")
        self.line_edit = QtWidgets.QLineEdit(self.value)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.line_edit)

        self.line_edit.editingFinished.connect(self.on_edit_finished)

    def on_edit_finished(self):
        new_value = self.line_edit.text()
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})
        self.value = new_value


class IntTypeWidget(QWidget):
    def __init__(self, name, type, value, mapModel, selectionRange, modelType, parent=None):
        super(IntTypeWidget, self).__init__(parent)
        self.name = name
        self.type = type
        try:
            self.value = int(value) if value != "Not Set" else 0
        except (ValueError, TypeError):
            self.value = 0
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        layout = QHBoxLayout()
        self.setLayout(layout)

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")
        self.spin_box = QtWidgets.QSpinBox()
        self.spin_box.setValue(self.value)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.spin_box)

        self.spin_box.valueChanged.connect(self.on_value_changed)

    def on_value_changed(self, new_value):
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})
        self.value = new_value


class BoolTypeWidget(QWidget):
    def __init__(self, name, type, value, mapModel, selectionRange, modelType, parent=None):
        super(BoolTypeWidget, self).__init__(parent)
        self.name = name
        self.type = type
        if isinstance(value, bool):
            self.value = value
        elif isinstance(value, str):
            self.value = value.lower() in ("true", "1", "yes")
        else:
            self.value = False
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        layout = QHBoxLayout()
        self.setLayout(layout)

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.value)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.checkbox)

        self.checkbox.stateChanged.connect(self.on_state_changed)

    def on_state_changed(self, state):
        new_value = bool(self.checkbox.isChecked())
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})
        self.value = new_value


class StringArrayTypeWidget(QWidget):
    def __init__(self, name, type, value, mapModel, selectionRange, modelType, parent=None):
        super(StringArrayTypeWidget, self).__init__(parent)
        self.name = name
        self.type = type
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        if isinstance(value, list):
            display = ", ".join(str(v) for v in value)
        elif value and value != "Not Set":
            display = str(value)
        else:
            display = ""

        layout = QHBoxLayout()
        self.setLayout(layout)

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")
        self.line_edit = QtWidgets.QLineEdit(display)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.line_edit)

        self.line_edit.editingFinished.connect(self.on_edit_finished)

    def on_edit_finished(self):
        text = self.line_edit.text().strip()
        new_value = [v.strip() for v in text.split(",") if v.strip()] if text else []
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})


class LootContainerTypeWidget(QWidget):
    def __init__(self, name, type, value, lootContainersCollection, mapModel, selectionRange, modelType, parent=None):
        super(LootContainerTypeWidget, self).__init__(parent)
        layout = QHBoxLayout()
        self.setLayout(layout)

        self.name = name
        self.type = type
        self.value = value if value != "Not Set" else ""
        self.lootContainersCollection = lootContainersCollection
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")

        self.combo_box = QtWidgets.QComboBox()
        self.combo_box.addItem("")
        for container_name in self.lootContainersCollection.allContainerTypes():
            self.combo_box.addItem(container_name)

        idx = self.combo_box.findText(self.value)
        if idx >= 0:
            self.combo_box.setCurrentIndex(idx)
        else:
            self.combo_box.setCurrentIndex(0)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.combo_box)

        self.combo_box.currentTextChanged.connect(self.on_selection_changed)

    def on_selection_changed(self, new_value):
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})
        self.value = new_value


class EnumTypeWidget(QWidget):
    def __init__(self, name, type, value, options, mapModel, selectionRange, modelType, parent=None):
        super(EnumTypeWidget, self).__init__(parent)
        layout = QHBoxLayout()
        self.setLayout(layout)

        self.name = name
        self.type = type
        self.value = value if value != "Not Set" else ""
        self.options = options if options else []
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        self.modelType = modelType

        name_label = QLabel(f"Name: {self.name}")
        type_label = QLabel(f"Type: {self.type}")

        self.combo_box = QtWidgets.QComboBox()
        for option in self.options:
            self.combo_box.addItem(option)

        idx = self.combo_box.findText(self.value)
        if idx >= 0:
            self.combo_box.setCurrentIndex(idx)
        else:
            self.combo_box.setCurrentIndex(0)

        layout.addWidget(name_label)
        layout.addWidget(type_label)
        layout.addWidget(self.combo_box)

        self.combo_box.currentTextChanged.connect(self.on_selection_changed)

    def on_selection_changed(self, new_value):
        self.mapModel.setGroupProperty(self.selectionRange, self.modelType, 'additionalProperties', {self.name: new_value})
        self.value = new_value


class AdditionalPropertiesDlg(QDialog):
    def __init__(self, objCollection, mapModel, texturesCollection, lootContainersCollection, selectionRange, modelType, parent=None):
        super(AdditionalPropertiesDlg, self).__init__(parent)
        self.setWindowTitle("Additional Properties")
        
        self.texturesCollection = texturesCollection
        self.lootContainersCollection = lootContainersCollection
        self.mapModel = mapModel
        self.selectionRange = selectionRange
        
        layout = QVBoxLayout()
        self.setLayout(layout)

        additionalProps = objCollection.getAdditionalProperties(modelType)

        for prop in additionalProps:
            selectedSquares = self.mapModel.getAllObjectOfType(modelType, self.selectionRange)
            propValue = None
            if selectedSquares:
                for square in selectedSquares:
                    for additional_prop in square.additional_properties:
                        if additional_prop.name == prop.name:
                            propValue = additional_prop.value
                            break
                    if propValue is not None:
                        break
            value_display = propValue if propValue is not None else "Not Set"

            if prop.type == "texture":
                widget = TextureTypeWidget(prop.name, prop.type, value_display, self.texturesCollection, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "lootContainer":
                widget = LootContainerTypeWidget(prop.name, prop.type, value_display, self.lootContainersCollection, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "string":
                widget = StringTypeWidget(prop.name, prop.type, value_display, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "int":
                widget = IntTypeWidget(prop.name, prop.type, value_display, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "bool":
                widget = BoolTypeWidget(prop.name, prop.type, value_display, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "stringArray":
                widget = StringArrayTypeWidget(prop.name, prop.type, value_display, self.mapModel, self.selectionRange, modelType)
            elif prop.type == "enum":
                widget = EnumTypeWidget(prop.name, prop.type, value_display, prop.options, self.mapModel, self.selectionRange, modelType)
            else:
                widget = UnknownTypeWidget(prop.name, prop.type, value_display)
            layout.addWidget(widget)
