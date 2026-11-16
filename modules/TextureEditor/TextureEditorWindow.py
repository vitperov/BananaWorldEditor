# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Texture editor window (early draft): pick a catalog texture or browse
# for an image file, preview it, check how it tiles (3 x 2 grid), apply
# a seamless conversion in memory and save it back over the texture
# file. The texture file is edited, never the icon.

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from modules.TextureEditor.SeamlessAlgorithms import ALGORITHMS
from modules.TextureEditor.TextureEditorModel import TextureEditorModel

CANVAS_SIZE = 256          # texture preview edge, pixels
CHECK_TILE = 128           # one tile in the seamless check grid
CHECK_COLUMNS, CHECK_ROWS = 3, 2


def imageToGrid(image: QImage):
    image = image.convertToFormat(QImage.Format_RGB32)
    grid = []
    for y in range(image.height()):
        row = []
        for x in range(image.width()):
            rgb = image.pixel(x, y)
            row.append(((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF))
        grid.append(row)
    return grid


def gridToImage(grid) -> QImage:
    height, width = len(grid), len(grid[0])
    image = QImage(width, height, QImage.Format_RGB32)
    for y, row in enumerate(grid):
        for x, (r, g, b) in enumerate(row):
            image.setPixel(x, y, 0xFF000000 | (r << 16) | (g << 8) | b)
    return image


class TextureEditorWindow(QWidget):

    def __init__(self, texturesCollection, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Texture Editor")
        self._textures = texturesCollection
        self._model = TextureEditorModel()

        # Left: every catalog texture; clicking opens its texture file
        # (not the icon). Browse covers files outside the catalogs.
        self._textureList = QListWidget()
        for name in sorted(texturesCollection.allTextureTypes()):
            item = QListWidgetItem(QIcon(texturesCollection.getIcon(name)), name)
            self._textureList.addItem(item)
        self._textureList.currentTextChanged.connect(self._openCatalogTexture)

        self._browseButton = QPushButton("Browse...")
        self._browseButton.clicked.connect(self._browse)
        self._saveButton = QPushButton("Save")
        self._saveButton.setEnabled(False)
        self._saveButton.clicked.connect(self._save)

        self._seamlessBox = QComboBox()
        self._seamlessBox.addItem(TextureEditorModel.ORIGINAL)
        for algorithm in ALGORITHMS:
            self._seamlessBox.addItem(algorithm.name)
        self._seamlessBox.currentTextChanged.connect(self._applyAlgorithm)

        self._fileLabel = QLabel("No texture loaded")
        self._canvas = QLabel()
        self._canvas.setFixedSize(CANVAS_SIZE, CANVAS_SIZE)
        self._canvas.setAlignment(Qt.AlignCenter)
        self._checkCanvas = QLabel()
        self._checkCanvas.setFixedSize(CHECK_TILE * CHECK_COLUMNS,
                                       CHECK_TILE * CHECK_ROWS)

        topRow = QHBoxLayout()
        topRow.addWidget(self._browseButton)
        topRow.addWidget(QLabel("Seamless:"))
        topRow.addWidget(self._seamlessBox)
        topRow.addStretch(1)
        topRow.addWidget(self._saveButton)

        right = QVBoxLayout()
        right.addLayout(topRow)
        right.addWidget(self._fileLabel)
        right.addWidget(self._canvas)
        right.addWidget(QLabel("Seamless check (3 x 2 tiles):"))
        right.addWidget(self._checkCanvas)
        right.addStretch(1)

        layout = QHBoxLayout()
        layout.addWidget(self._textureList, 1)
        layout.addLayout(right, 3)
        self.setLayout(layout)

    def _openCatalogTexture(self, name):
        if name:
            self._openFile(self._textures.getTextureFile(name))

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open texture image", "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All files (*)")
        if path:
            self._textureList.blockSignals(True)
            self._textureList.clearSelection()
            self._textureList.setCurrentItem(None)
            self._textureList.blockSignals(False)
            self._openFile(path)

    def _openFile(self, path):
        image = QImage(path) if path else QImage()
        if image.isNull():
            QMessageBox.critical(self, "Texture Editor",
                                 "Cannot load image:\n%s" % path)
            return
        self._model.open(imageToGrid(image), path)
        self._resetSeamlessBox()
        self._saveButton.setEnabled(True)
        self._fileLabel.setText(os.path.relpath(path))
        self._refreshCanvases()

    def _applyAlgorithm(self, name):
        if not self._model.isLoaded():
            return
        self._model.setAlgorithm(name)
        self._refreshCanvases()

    def _save(self):
        if not self._model.isLoaded():
            return
        image = gridToImage(self._model.current)
        if not image.save(self._model.filePath):
            QMessageBox.critical(self, "Texture Editor",
                                 "Cannot save:\n%s" % self._model.filePath)
            return
        # The saved image is the new original.
        self._model.markSaved()
        self._resetSeamlessBox()
        self._refreshCanvases()

    def _resetSeamlessBox(self):
        self._seamlessBox.blockSignals(True)
        self._seamlessBox.setCurrentIndex(0)
        self._seamlessBox.blockSignals(False)

    def _refreshCanvases(self):
        pixmap = QPixmap.fromImage(gridToImage(self._model.current))
        self._canvas.setPixmap(pixmap.scaled(
            CANVAS_SIZE, CANVAS_SIZE,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))

        tile = pixmap.scaled(CHECK_TILE, CHECK_TILE,
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        grid = QPixmap(CHECK_TILE * CHECK_COLUMNS, CHECK_TILE * CHECK_ROWS)
        painter = QPainter(grid)
        for row in range(CHECK_ROWS):
            for column in range(CHECK_COLUMNS):
                painter.drawPixmap(column * CHECK_TILE, row * CHECK_TILE, tile)
        painter.end()
        self._checkCanvas.setPixmap(grid)
