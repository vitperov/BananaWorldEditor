# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# State of the texture editor: the image being edited (as a pixel grid,
# see SeamlessAlgorithms), the file it came from and the seamless
# conversion currently applied. No Qt dependencies; the window does the
# QImage/file work.

from typing import Optional

from modules.TextureEditor.SeamlessAlgorithms import Grid, algorithmByName


class TextureEditorModel:
    # Dropdown entry meaning "no conversion". After a save the saved
    # image is the new original, so the selection falls back to this.
    ORIGINAL = 'Original'

    def __init__(self):
        self.filePath: Optional[str] = None
        self.original: Optional[Grid] = None
        self.current: Optional[Grid] = None
        self.algorithmName = self.ORIGINAL

    def isLoaded(self) -> bool:
        return self.original is not None

    def open(self, pixels: Grid, filePath: str):
        self.filePath = filePath
        self.original = pixels
        self.current = pixels
        self.algorithmName = self.ORIGINAL

    def setAlgorithm(self, name: str):
        """Convert the original in memory; nothing touches the file."""
        if not self.isLoaded():
            return
        self.algorithmName = name
        if name == self.ORIGINAL:
            self.current = self.original
        else:
            self.current = algorithmByName(name).apply(self.original)

    def markSaved(self):
        """The current image was written to filePath: it is the new
        original and the conversion selection resets."""
        self.original = self.current
        self.algorithmName = self.ORIGINAL
