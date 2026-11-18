# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Texture editor window (early draft): pick a catalog texture or browse
# for an image file, preview it, check how it tiles (3 x 2 grid), apply
# a seamless conversion in memory and save it back over the texture
# file. The texture file is edited, never the icon.
#
# Layout: texture list | preview column | seamless check. The preview
# column holds the fixed-size texture preview and, under it, the
# pipeline controls top-down in run order: "Pre-filters" (checkboxes,
# the fixed run order is internal) then "Seamless algorithm". Each
# filter's user-facing hint (stored in the filter model) is a tooltip on
# the checkbox and on an (i) button next to it; clicking (i) shows it. The
# seamless check takes all remaining window space, so enlarging the
# window enlarges the tiled picture.
#
# The pipeline runs in a PipelineThread so the window stays responsive
# on large textures; a busy bar with the current step shows in the top
# row. Changing an option mid-run lets the run finish, drops its
# (now stale) result and starts one for the latest selection.

import html
import os

import numpy as np
from PyQt5.QtCore import QPoint, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QGroupBox,
                             QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QMessageBox, QProgressBar,
                             QPushButton, QSizePolicy, QStyle, QToolButton,
                             QToolTip, QVBoxLayout, QWidget)

from modules.TextureEditor.PreFilters import FILTERS
from modules.TextureEditor.SeamlessAlgorithms import ALGORITHMS
from modules.TextureEditor.TextureEditorModel import TextureEditorModel

CANVAS_SIZE = 256          # texture preview edge, pixels
CHECK_MIN_TILE = 128       # smallest tile in the seamless check grid
CHECK_COLUMNS, CHECK_ROWS = 3, 2


# Format_RGB32 pixels are 0xFFRRGGBB words: bytes B, G, R, 0xFF on the
# little-endian machines the editor runs on.

def imageToArray(image: QImage) -> np.ndarray:
    """QImage -> (height, width, 3) uint8 RGB array (a copy)."""
    image = image.convertToFormat(QImage.Format_RGB32)
    width, height = image.width(), image.height()
    bits = image.constBits()
    bits.setsize(image.bytesPerLine() * height)
    rows = np.frombuffer(bits, np.uint8).reshape(height, image.bytesPerLine())
    bgra = rows[:, :width * 4].reshape(height, width, 4)
    return np.ascontiguousarray(bgra[..., 2::-1])


def arrayToImage(rgb: np.ndarray) -> QImage:
    height, width = rgb.shape[:2]
    bgra = np.empty((height, width, 4), np.uint8)
    bgra[..., :3] = rgb[..., ::-1]
    bgra[..., 3] = 255
    # copy(): the QImage must own its pixels, not borrow the array's.
    return QImage(bgra.data, width, height, width * 4,
                  QImage.Format_RGB32).copy()


def hintHtml(text: str) -> str:
    """Rich text makes Qt word-wrap a long tooltip instead of showing
    one very wide line."""
    return "<p>%s</p>" % html.escape(text)


class InfoButton(QToolButton):
    """Small (i) icon next to an option: hovering shows its hint as a
    tooltip, clicking shows it at once."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
        self.setAutoRaise(True)
        self.setCursor(Qt.WhatsThisCursor)
        self.setToolTip(hintHtml(text))
        self.clicked.connect(self._showHint)

    def _showHint(self):
        QToolTip.showText(self.mapToGlobal(QPoint(0, self.height())),
                          self.toolTip(), self)


class PipelineThread(QThread):
    """Runs one PipelineJob and turns its result into a QImage (QImage,
    unlike QPixmap, may be built outside the GUI thread)."""

    stepStarted = pyqtSignal(int, int, str)

    def __init__(self, job, parent=None):
        super().__init__(parent)
        self.job = job
        self.image = None

    def run(self):
        self.job.run(self.stepStarted.emit)
        self.image = arrayToImage(self.job.current)


class SeamlessCheckCanvas(QWidget):
    """Tiles one texture CHECK_COLUMNS x CHECK_ROWS times, as large as the
    widget allows while keeping the grid's aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._source = QPixmap()
        self.setMinimumSize(CHECK_MIN_TILE * CHECK_COLUMNS,
                            CHECK_MIN_TILE * CHECK_ROWS)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setTexture(self, pixmap: QPixmap):
        self._source = pixmap
        self.update()

    def tileSize(self) -> int:
        return max(1, min(self.width() // CHECK_COLUMNS,
                          self.height() // CHECK_ROWS))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())
        if self._source.isNull():
            painter.end()
            return
        tileSize = self.tileSize()
        tile = self._source.scaled(tileSize, tileSize, Qt.IgnoreAspectRatio,
                                   Qt.SmoothTransformation)
        # Anchored top-left so the grid sits right under its label.
        for row in range(CHECK_ROWS):
            for column in range(CHECK_COLUMNS):
                painter.drawPixmap(column * tileSize, row * tileSize, tile)
        painter.end()


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

        self._filterBoxes = []
        for prefilter in FILTERS:
            box = QCheckBox(prefilter.name)
            box.setToolTip(hintHtml(prefilter.description))
            box.toggled.connect(
                lambda on, name=prefilter.name: self._toggleFilter(name, on))
            self._filterBoxes.append(box)

        self._thread = None
        self._busyLabel = QLabel()
        self._busyBar = QProgressBar()
        self._busyBar.setRange(0, 0)        # animated "working" bar
        self._busyBar.setTextVisible(False)
        self._busyBar.setFixedWidth(160)
        self._setBusy(False)

        self._fileLabel = QLabel("No texture loaded")
        # A long path (browsed file far from the repo) must not widen the
        # window; it is clipped and the full path is in the tooltip.
        self._fileLabel.setSizePolicy(QSizePolicy.Ignored,
                                      QSizePolicy.Preferred)
        self._canvas = QLabel()
        self._canvas.setFixedSize(CANVAS_SIZE, CANVAS_SIZE)
        self._canvas.setAlignment(Qt.AlignCenter)
        self._checkCanvas = SeamlessCheckCanvas()

        topRow = QHBoxLayout()
        topRow.addWidget(self._browseButton)
        topRow.addStretch(1)
        topRow.addWidget(self._busyLabel)
        topRow.addWidget(self._busyBar)
        topRow.addWidget(self._saveButton)

        # Preview column stays at its fixed size; the check canvas next to
        # it grows with the window.
        previewColumn = QVBoxLayout()
        previewColumn.addWidget(QLabel("Texture:"))
        previewColumn.addWidget(self._canvas)
        previewColumn.addWidget(self._filtersGroup())
        previewColumn.addWidget(self._algorithmGroup())
        previewColumn.addStretch(1)

        checkColumn = QVBoxLayout()
        checkColumn.addWidget(QLabel("Seamless check (%d x %d tiles):"
                                     % (CHECK_COLUMNS, CHECK_ROWS)))
        checkColumn.addWidget(self._checkCanvas, 1)

        canvasRow = QHBoxLayout()
        canvasRow.addLayout(previewColumn)
        canvasRow.addLayout(checkColumn, 1)

        right = QVBoxLayout()
        right.addLayout(topRow)
        right.addWidget(self._fileLabel)
        right.addLayout(canvasRow, 1)

        layout = QHBoxLayout()
        layout.addWidget(self._textureList)
        layout.addLayout(right, 1)
        self.setLayout(layout)
        self._textureList.setMaximumWidth(220)
        self.resize(1280, 720)

    def _filtersGroup(self) -> QGroupBox:
        group = QGroupBox("Pre-filters")
        column = QVBoxLayout()
        for box, prefilter in zip(self._filterBoxes, FILTERS):
            row = QHBoxLayout()
            row.addWidget(box)
            row.addWidget(InfoButton(prefilter.description))
            row.addStretch(1)
            column.addLayout(row)
        group.setLayout(column)
        return group

    def _algorithmGroup(self) -> QGroupBox:
        group = QGroupBox("Seamless algorithm")
        column = QVBoxLayout()
        column.addWidget(self._seamlessBox)
        group.setLayout(column)
        return group

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
        self._model.open(imageToArray(image), path)
        self._resetControls()
        self._saveButton.setEnabled(True)
        self._fileLabel.setToolTip(os.path.abspath(path))
        self._showImage(arrayToImage(self._model.current))

    def _fileText(self, image: QImage) -> str:
        """Path and size; the new size too when a filter cropped it."""
        height, width = self._model.original.shape[:2]
        text = "%s   %d x %d" % (os.path.relpath(self._model.filePath), width, height)
        if (image.width(), image.height()) != (width, height):
            text += "  ->  %d x %d" % (image.width(), image.height())
        return text

    def _applyAlgorithm(self, name):
        self._model.setAlgorithm(name)
        self._recompute()

    def _save(self):
        if not self._model.isLoaded() or not self._model.isUpToDate():
            return
        image = arrayToImage(self._model.current)
        if not image.save(self._model.filePath):
            QMessageBox.critical(self, "Texture Editor",
                                 "Cannot save:\n%s" % self._model.filePath)
            return
        # The saved image is the new original.
        self._model.markSaved()
        self._resetControls()
        self._showImage(image)

    def _toggleFilter(self, name, enabled):
        self._model.setFilterEnabled(name, enabled)
        self._recompute()

    def _recompute(self):
        """Bring the picture in line with the selection, in the
        background. While a run is busy nothing starts: its finish
        handler sees the newer selection and starts the next run."""
        if self._thread is not None:
            return
        if not self._model.isLoaded() or self._model.isUpToDate():
            self._setBusy(False)
            return
        self._thread = PipelineThread(self._model.makeJob(), self)
        self._thread.stepStarted.connect(self._onStep)
        self._thread.finished.connect(self._onFinished)
        self._setBusy(True)
        self._thread.start()

    def _onStep(self, index, count, label):
        if index < count:
            self._busyLabel.setText("Step %d of %d: %s..." % (index + 1, count, label))

    def _onFinished(self):
        thread, self._thread = self._thread, None
        if self._model.acceptResult(thread.job):
            self._showImage(thread.image)
        thread.deleteLater()
        self._recompute()

    def _setBusy(self, busy):
        self._busyLabel.setVisible(busy)
        self._busyBar.setVisible(busy)
        self._saveButton.setEnabled(not busy and self._model.isLoaded())
        if busy:
            self._busyLabel.setText("Working...")

    def closeEvent(self, event):
        # A QThread must not be destroyed while running.
        if self._thread is not None:
            self._thread.wait()
        super().closeEvent(event)

    def _resetControls(self):
        """Mirror the model after open/save: no filters, Original."""
        for widget in [self._seamlessBox] + self._filterBoxes:
            widget.blockSignals(True)
        self._seamlessBox.setCurrentIndex(0)
        for box in self._filterBoxes:
            box.setChecked(False)
        for widget in [self._seamlessBox] + self._filterBoxes:
            widget.blockSignals(False)

    def _showImage(self, image: QImage):
        self._fileLabel.setText(self._fileText(image))
        pixmap = QPixmap.fromImage(image)
        self._canvas.setPixmap(pixmap.scaled(
            CANVAS_SIZE, CANVAS_SIZE,
            Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self._checkCanvas.setTexture(pixmap)
