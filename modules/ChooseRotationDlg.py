# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout
from functools import partial
from modules.SimpleSquareItem import SimpleSquareItem

class ChooseRotationDlg(QDialog):
    def __init__(self, itemModel, objCollection, tilesize, parent=None):
        super(ChooseRotationDlg, self).__init__(parent)
        self.setWindowTitle("Choose Rotation")
        self.selectedRotation = None
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        rotations = [0, 90, 180, 270]
        
        for rotation in rotations:
            itemModel.setProperty('rotation', str(rotation))
            simpleSquareItem = SimpleSquareItem(itemModel, objCollection, tilesize)
            layout.addWidget(simpleSquareItem)
            
            btn = QPushButton(f"Rotation {rotation}")
            btn.clicked.connect(partial(self.onButtonClicked, rotation))
            layout.addWidget(btn)
    
    def onButtonClicked(self, rotation):
        self.selectedRotation = rotation
        self.accept()
