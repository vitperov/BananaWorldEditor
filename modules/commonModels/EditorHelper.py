# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from .ObjectRotation import *

class EditorHelper:
    def __init__(self, model):
        self._model = model

    def generateWallFrame(self, selectionRange):
        if not selectionRange:
            return
            
        start_col = selectionRange.startCol
        start_row = selectionRange.startRow
        end_col = selectionRange.endCol
        end_row = selectionRange.endRow
        z_level = selectionRange.zLevel
        check_objects = ["Wall", "Corner", "Window"]

        # Top row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, start_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("Corner")
                obj.setProperty('rotation', ObjectRotation.deg0)
            elif col == end_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("Corner")
                obj.setProperty('rotation', ObjectRotation.deg90)
            else:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("Wall")
                obj.setProperty('rotation', ObjectRotation.deg0)

        # Bottom row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, end_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("Corner")
                obj.setProperty('rotation', ObjectRotation.deg270)
            elif col == end_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("Corner")
                obj.setProperty('rotation', ObjectRotation.deg180)
            else:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("Wall")
                obj.setProperty('rotation', ObjectRotation.deg180)

        # Left column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(start_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(start_col, row, z_level)
            obj.setModel("Wall")
            obj.setProperty('rotation', ObjectRotation.deg270)

        # Right column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(end_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(end_col, row, z_level)
            obj.setModel("Wall")
            obj.setProperty('rotation', ObjectRotation.deg90)

    def generateRoofFrame(self, selectionRange):
        if not selectionRange:
            return
            
        start_col = selectionRange.startCol
        start_row = selectionRange.startRow
        end_col = selectionRange.endCol
        end_row = selectionRange.endRow
        z_level = selectionRange.zLevel
        check_objects = ["PitchedRoof", "RoofCorner", "PitchedRoofHalf", "RoofCornerHalf",  "FlatRoof"]

        # Top row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, start_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("RoofCorner")
                obj.setProperty('rotation', ObjectRotation.deg0)
            elif col == end_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("RoofCorner")
                obj.setProperty('rotation', ObjectRotation.deg90)
            else:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("PitchedRoof")
                obj.setProperty('rotation', ObjectRotation.deg0)

        # Bottom row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, end_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("RoofCorner")
                obj.setProperty('rotation', ObjectRotation.deg270)
            elif col == end_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("RoofCorner")
                obj.setProperty('rotation', ObjectRotation.deg180)
            else:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("PitchedRoof")
                obj.setProperty('rotation', ObjectRotation.deg180)

        # Left column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(start_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(start_col, row, z_level)
            obj.setModel("PitchedRoof")
            obj.setProperty('rotation', ObjectRotation.deg270)

        # Right column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(end_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(end_col, row, z_level)
            obj.setModel("PitchedRoof")
            obj.setProperty('rotation', ObjectRotation.deg90)

    def generateRoofFrameHalf(self, selectionRange):
        if not selectionRange:
            return
            
        start_col = selectionRange.startCol
        start_row = selectionRange.startRow
        end_col = selectionRange.endCol
        end_row = selectionRange.endRow
        z_level = selectionRange.zLevel
        check_objects = ["PitchedRoof", "RoofCorner", "PitchedRoofHalf", "RoofCornerHalf",  "FlatRoof"]

        # Top row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, start_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("RoofCornerHalf")
                obj.setProperty('rotation', ObjectRotation.deg0)
            elif col == end_col and start_row == start_row:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("RoofCornerHalf")
                obj.setProperty('rotation', ObjectRotation.deg90)
            else:
                obj = self._model.createObjectAt(col, start_row, z_level)
                obj.setModel("PitchedRoofHalf")
                obj.setProperty('rotation', ObjectRotation.deg0)

        # Bottom row
        for col in range(start_col, end_col + 1):
            existing = self._model.getSquareItems(col, end_row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            if col == start_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("RoofCornerHalf")
                obj.setProperty('rotation', ObjectRotation.deg270)
            elif col == end_col and end_row == end_row:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("RoofCornerHalf")
                obj.setProperty('rotation', ObjectRotation.deg180)
            else:
                obj = self._model.createObjectAt(col, end_row, z_level)
                obj.setModel("PitchedRoofHalf")
                obj.setProperty('rotation', ObjectRotation.deg180)

        # Left column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(start_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(start_col, row, z_level)
            obj.setModel("PitchedRoofHalf")
            obj.setProperty('rotation', ObjectRotation.deg270)

        # Right column
        for row in range(start_row + 1, end_row):
            existing = self._model.getSquareItems(end_col, row, z_level)
            if any(sq.properties.get('model') in check_objects for sq in existing):
                continue
            obj = self._model.createObjectAt(end_col, row, z_level)
            obj.setModel("PitchedRoofHalf")
            obj.setProperty('rotation', ObjectRotation.deg90)
