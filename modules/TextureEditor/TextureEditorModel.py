# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# State of the texture editor: the image being edited (as a pixel grid,
# see SeamlessAlgorithms), the file it came from, the enabled
# pre-filters and the seamless conversion currently applied.
# Pipeline: original -> enabled pre-filters (fixed order) -> algorithm.
# No Qt dependencies; the window does the QImage/file work.
#
# Computing is split from state so it can run off the GUI thread:
# makeJob() snapshots the state into a PipelineJob, job.run() does the
# work (safe in any thread, touches no model state) and acceptResult()
# stores it only if the state has not changed meanwhile. recompute()
# does all three inline.

from typing import Callable, FrozenSet, Optional, Set

from modules.TextureEditor.PreFilters import FILTERS
from modules.TextureEditor.SeamlessAlgorithms import Grid, algorithmByName

# progress(stepIndex, stepCount, stepLabel), called before each step.
Progress = Callable[[int, int, str], None]


class PipelineJob:
    """One run of the pipeline on a snapshot of the model state."""

    def __init__(self, version: int, original: Grid,
                 filterNames: FrozenSet[str], algorithmName: str,
                 cachedFiltered: Optional[Grid]):
        self.version = version
        self.filterNames = filterNames
        self.algorithmName = algorithmName
        self._original = original
        self._cachedFiltered = cachedFiltered
        self.filtered: Optional[Grid] = None
        self.current: Optional[Grid] = None

    def steps(self):
        names = []
        if self._cachedFiltered is None:
            names += [f.name for f in FILTERS if f.name in self.filterNames]
        if self.algorithmName != TextureEditorModel.ORIGINAL:
            names.append(self.algorithmName)
        return names

    def run(self, progress: Optional[Progress] = None):
        steps = self.steps()
        step = 0

        def report(label):
            if progress:
                progress(step, len(steps), label)

        grid = self._cachedFiltered
        if grid is None:
            grid = self._original
            for prefilter in FILTERS:
                if prefilter.name in self.filterNames:
                    report(prefilter.name)
                    grid = prefilter.apply(grid)
                    step += 1
        self.filtered = grid
        if self.algorithmName != TextureEditorModel.ORIGINAL:
            report(self.algorithmName)
            grid = algorithmByName(self.algorithmName).apply(grid)
            step += 1
        self.current = grid
        if progress:
            progress(step, len(steps), "Done")


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
        # Bumped on every state change; a job's result is accepted only
        # if its version is still current.
        self.version = 0
        # Original after the pre-filters, for the filter set it was made
        # with: switching the algorithm reuses it.
        self._filtered: Optional[Grid] = None
        self._filteredFor: Optional[FrozenSet[str]] = None
        self._currentVersion = 0

    def isLoaded(self) -> bool:
        return self.original is not None

    def isUpToDate(self) -> bool:
        """current matches the selected filters and algorithm."""
        return self._currentVersion == self.version

    def open(self, pixels: Grid, filePath: str):
        self.filePath = filePath
        self.original = pixels
        self._reset()

    def setAlgorithm(self, name: str):
        """Select a conversion; nothing touches the file. current is
        stale until a job for the new state is accepted."""
        self.algorithmName = name
        self.version += 1

    def setFilterEnabled(self, name: str, enabled: bool):
        if enabled:
            self.enabledFilters.add(name)
        else:
            self.enabledFilters.discard(name)
        self.version += 1

    def makeJob(self) -> PipelineJob:
        filters = frozenset(self.enabledFilters)
        cached = self._filtered if self._filteredFor == filters else None
        return PipelineJob(self.version, self.original, filters,
                           self.algorithmName, cached)

    def acceptResult(self, job: PipelineJob) -> bool:
        if job.version != self.version:
            return False
        self._filtered, self._filteredFor = job.filtered, job.filterNames
        self.current = job.current
        self._currentVersion = job.version
        return True

    def recompute(self):
        """Run the pipeline inline (tests, scripts)."""
        if self.isLoaded() and not self.isUpToDate():
            job = self.makeJob()
            job.run()
            self.acceptResult(job)

    def markSaved(self):
        """The current image was written to filePath: it is the new
        original, the filters and the conversion selection reset (they
        are baked into the saved image)."""
        self.original = self.current
        self._reset()

    def _reset(self):
        self.algorithmName = self.ORIGINAL
        self.enabledFilters = set()
        self.version += 1
        self._filtered, self._filteredFor = self.original, frozenset()
        self.current = self.original
        self._currentVersion = self.version
