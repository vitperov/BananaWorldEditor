# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Texture editor model: the pipeline result follows the selection, a
# stale background job is rejected, and the filtered image is reused
# when only the algorithm changes.
#
# Run from the repository root:
#   python3 -m unittest discover -s tests

import os
import sys
import unittest

import numpy as np

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from modules.TextureEditor.PreFilters import LightingFlatten, applyFilters
from modules.TextureEditor.SeamlessAlgorithms import MirrorFold
from modules.TextureEditor.TextureEditorModel import TextureEditorModel

FILTER = LightingFlatten.name
ALGORITHM = MirrorFold.name


def picture(size=16):
    y, x = np.mgrid[0:size, 0:size]
    return np.stack([x * 15, y * 15, (x + y) * 7], axis=-1).astype(np.uint8)


def loaded():
    model = TextureEditorModel()
    model.open(picture(), 'unused.png')
    return model


class TextureEditorModelTest(unittest.TestCase):

    def test_open_is_up_to_date_original(self):
        model = loaded()
        self.assertTrue(model.isUpToDate())
        self.assertIs(model.current, model.original)

    def test_pipeline_is_filters_then_algorithm(self):
        model = loaded()
        model.setFilterEnabled(FILTER, True)
        model.setAlgorithm(ALGORITHM)
        self.assertFalse(model.isUpToDate())
        model.recompute()
        expected = MirrorFold().apply(applyFilters(picture(), {FILTER}))
        np.testing.assert_array_equal(model.current, expected)

    def test_stale_job_rejected(self):
        model = loaded()
        model.setFilterEnabled(FILTER, True)
        job = model.makeJob()
        model.setAlgorithm(ALGORITHM)       # user changed mind meanwhile
        job.run()
        self.assertFalse(model.acceptResult(job))
        self.assertFalse(model.isUpToDate())

    def test_algorithm_change_reuses_filtered(self):
        model = loaded()
        model.setFilterEnabled(FILTER, True)
        model.recompute()
        model.setAlgorithm(ALGORITHM)
        self.assertEqual(model.makeJob().steps(), [ALGORITHM])

    def test_progress_reports_every_step(self):
        model = loaded()
        model.setFilterEnabled(FILTER, True)
        model.setAlgorithm(ALGORITHM)
        calls = []
        model.makeJob().run(lambda i, n, label: calls.append((i, n, label)))
        self.assertEqual(calls, [(0, 2, FILTER), (1, 2, ALGORITHM),
                                 (2, 2, "Done")])

    def test_save_bakes_and_resets(self):
        model = loaded()
        model.setFilterEnabled(FILTER, True)
        model.recompute()
        result = model.current
        model.markSaved()
        self.assertIs(model.original, result)
        self.assertEqual(model.enabledFilters, set())
        self.assertTrue(model.isUpToDate())


if __name__ == '__main__':
    unittest.main()
