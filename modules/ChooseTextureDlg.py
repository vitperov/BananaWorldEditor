# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton, QLabel, QGridLayout, QSpacerItem, QSizePolicy
from PyQt5 import QtGui, QtCore
from PyQt5.QtCore import QSize
from functools import partial

class ChooseTextureDlg(QDialog):
    def __init__(self, texturesCollection, parent=None):
        super(ChooseTextureDlg, self).__init__(parent)
        self.setWindowTitle("Choose Texture")
        self.selectedTexture = None
        
        self.texturesCollection = texturesCollection

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.gridLayout = QGridLayout()
        layout.addLayout(self.gridLayout)
        
        allTextures = self.texturesCollection.allTextureTypes()
        
        col_count = 4
        for index, texture in enumerate(allTextures):
            row = index // col_count
            col = index % col_count
            
            itemLayout = QVBoxLayout()
            
            label = QLabel(f"{texture}")
            itemLayout.addWidget(label)
            
            btn = QPushButton()
            self.updatePixmap(btn, texture)
            btn.clicked.connect(partial(self.onButtonClicked, texture))
            itemLayout.addWidget(btn)
            
            self.gridLayout.addLayout(itemLayout, row, col)
        
        last_row = (len(allTextures) // col_count) + 1
        verticalSpacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.gridLayout.addItem(verticalSpacer, last_row, 0, 1, col_count)

    def updatePixmap(self, button, texture):
        imgFile = self.texturesCollection.getIcon(texture)
        try:
            pixmap = QtGui.QPixmap(imgFile, "1")
        except:
            pixmap = QtGui.QPixmap(imgFile)
        
        size = QSize(64, 64)
        scaledPixmap = pixmap.scaled(size, QtCore.Qt.KeepAspectRatio)
        
        button.setIcon(QtGui.QIcon(scaledPixmap))
        button.setIconSize(size)

    def onButtonClicked(self, texture):
        self.selectedTexture = texture
        self.accept()
