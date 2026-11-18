# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# State of the texture editor: the image being edited (as a pixel grid,
# see SeamlessAlgorithms), the file it came from, the enabled
# pre-filters and the seamless conversion currently applied.
# Pipeline: original -> enabled pre-filters (fixed order) -> algorithm.
# No Qt dependencies; the window does the QImage/file work.

from typing import Optional, Set

from modules.TextureEditor.PreFilters import applyFilters
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
        self.enabledFilters: Set[str] = set()
        # Original after the pre-filters: switching the algorithm reuses
        # it instead of re-running the filters.
        self._filtered: Optional[Grid] = None

    def isLoaded(self) -> bool:
        return self.original is not None

    def open(self, pixels: Grid, filePath: str):
        self.filePath = filePath
        self.original = pixels
        self._reset()

    def setAlgorithm(self, name: str):
        """Convert the filtered original in memory; nothing touches the
        file."""
        self.algorithmName = name
        self._runAlgorithm()

    def setFilterEnabled(self, name: str, enabled: bool):
        if enabled:
            self.enabledFilters.add(name)
        else:
            self.enabledFilters.discard(name)
        self._filtered = None
        self._runAlgorithm()

    def markSaved(self):
        """The current image was written to filePath: it is the new
        original, the filters and the conversion selection reset (they
        are baked into the saved image)."""
        self.original = self.current
        self._reset()

    def _reset(self):
        self.algorithmName = self.ORIGINAL
        self.enabledFilters = set()
        self._filtered = self.original
        self.current = self.original

    def _runAlgorithm(self):
        if not self.isLoaded():
            return
        if self._filtered is None:
            self._filtered = applyFilters(self.original, self.enabledFilters)
        if self.algorithmName == self.ORIGINAL:
            self.current = self._filtered
        else:
            self.current = algorithmByName(self.algorithmName).apply(self._filtered)
