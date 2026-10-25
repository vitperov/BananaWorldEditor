from PyQt5.QtCore import *

import traceback
import json

from modules.GeometryPrimitives import *
from modules.commonModels.MapObjectModelGeneral import *
from modules.commonModels.SelectionRange import *

class MapModelGeneral(QObject):
    updatedEntireMap = pyqtSignal()
    # Emitted when the map's on-disk identity changes (opened, saved, or reset
    # by newMap). Carries the file path, or '' when the map has no file yet.
    currentFileChanged = pyqtSignal(str)

    def __init__(self, squareModel, objCollection, texturesCollection, lootContainersCollection=None, basePrefab=None):
        QObject.__init__(self)
        self._sqareModel = squareModel
        self._objCollection = objCollection
        self._texturesCollection = texturesCollection
        self._lootContainersCollection = lootContainersCollection
        self.width = 0
        self.height = 0
        self.editorWidth = 0
        self.editorHeight = 0;
        self._squares = list()
        # Hint to the runtime loader (CompoundObjectLoader): name of the
        # base prefab to instantiate as the compound's root, or None for an
        # empty GameObject root. Set per editor type (e.g. "House" for the
        # House editor; None for Terrain). Round-trips through JSON.
        self.basePrefab = basePrefab
        # Height of a single floor, in relative z units. Used by the runtime to
        # decide which floor an object (or the player) belongs to. Only
        # meaningful for buildings, so it is serialized for house maps only
        # (basePrefab set) and defaults to 1.0.
        self.floorHeight = 1.0
        self._updateCallback = self.updateEntireMap
        # File this map lives in, and a hash of its contents as last written
        # there. Together they drive the title bar and let Save skip the dialog.
        # The empty map an editor opens with counts as saved - there is nothing
        # in it to lose - so it starts out clean rather than flagged as dirty.
        self._currentFilePath = None
        self._savedSnapshot = self._snapshot()

    def setUpdatedCallback(self, callback):
        self._updateCallback = callback

    def newMap(self, w, h):
        self.width = w
        self.height = h
        for row in range(h):
            for column in range(w):
                self.createEmpySquareAt(row, column)

        # A brand new map belongs to no file yet, and an untouched blank one has
        # nothing to lose - so it starts clean, and Save will ask for a name.
        self._currentFilePath = None
        self._savedSnapshot = self._snapshot()
        self.currentFileChanged.emit('')

        if self._updateCallback is not None:
            self._updateCallback()

    def getSquare(self, x, y):
        for square in self._squares:
            if square.x == x and square.y == y:
                return square

        return None

    def getSquareItems(self, x, y, z):
        items = list()
        for square in self._squares:
            if square.x == x and square.y == y and square.z == z:
                items.append(square)
        return items

    def getAreaSquareUniqueItems(self, selectionRange):
        items = list()
        seen_models = set()
        for square in self._squares:
            if selectionRange.startCol <= square.x <= selectionRange.endCol and selectionRange.startRow <= square.y <= selectionRange.endRow and square.z == selectionRange.zLevel:
                model = square.properties['model']
                if model not in seen_models:
                    seen_models.add(model)
                    items.append(square)
        return items

    def deleteSquareById(self, id):
        print("Deleting entire square, id=" + str(id))
        N = len(self._squares);
        for i in range(N):
            if self._squares[i].id == id:
                del self._squares[i]
                if self._updateCallback is not None:
                    self._updateCallback()
                return

    def createEmpySquareAt(self, row, column):
        obj = self._sqareModel()
        obj.y = row
        obj.x = column
        self._squares.append(obj)

    def createObjectAt(self, x, y, z):
        obj = self._sqareModel()
        obj.x = x
        obj.y = y
        obj.z = z
        self._squares.append(obj)
        return obj

    def addMapObject(self, obj):
        self._squares.append(obj)
    
    def createObjectsInSelection(self, selectionRange):
        for row in range(selectionRange.startRow, selectionRange.endRow + 1):
            for col in range(selectionRange.startCol, selectionRange.endCol + 1):
                self.createObjectAt(col, row, selectionRange.zLevel)

    def deleteObjectsInSelection(self, selectionRange, model=None):
        i = 0
        while i < len(self._squares):
            square = self._squares[i]
            if (selectionRange.startCol <= square.x <= selectionRange.endCol and 
                selectionRange.startRow <= square.y <= selectionRange.endRow and 
                square.z == selectionRange.zLevel and
                (model is None or square.properties['model'] == model)):
                del self._squares[i]
            else:
                i += 1

        if self._updateCallback:
            self._updateCallback()

    def removeAllMapObjects(self, model):
        before = len(self._squares)
        self._squares[:] = [sq for sq in self._squares if sq.properties.get('model') != model]
        return (before - len(self._squares)) > 0

    # addRow / addColumn / deleteRow / deleteColumn are thin adapters over the
    # insertLine / removeLine engine below (single line, empty fill), so the
    # GUI toolbar and the bwe_cli CLI share one implementation.
    def addRow(self, before=None):
        self.insertLine('row', self.height if before is None else before, count=1)

    def addColumn(self, before=None):
        self.insertLine('col', self.width if before is None else before, count=1)

    def deleteRow(self, rowId):
        self.removeLine('row', rowId, count=1)

    def deleteColumn(self, columnId):
        self.removeLine('col', columnId, count=1)

    def getAllSquares(self, zLevel):
        items = list()
        for square in self._squares:
            if square.z == zLevel:
                items.append(square)
        return items

    def getSquares(self):
        """Public read-only accessor for every square (all z-levels), so
        callers (CLI dump/describe, renderer) do not reach into _squares."""
        return self._squares
        
    def getAllObjectOfType(self, modelType, selectionRange=None):
        result = []
        for obj in self._squares:
            isInSelectionRange = (selectionRange is None or
                                  (selectionRange.startCol <= obj.x <= selectionRange.endCol and
                                   selectionRange.startRow <= obj.y <= selectionRange.endRow and
                                   obj.z == selectionRange.zLevel))
            if isInSelectionRange and (modelType is None or obj.properties.get('model') == modelType):
                result.append(obj)
        return result

    def size(self):
        return [self.height, self.width]

    def toSerializableObj(self):
        squares = list()
        for square in self._squares:
            squares.append(square.toSerializableObj())

        obj = dict()
        obj['version'] = 1
        if self.basePrefab is not None:
            obj['basePrefab'] = self.basePrefab
            obj['floorHeight'] = self.floorHeight
        obj['squares'] = squares
        obj['width']   = self.width
        obj['height']  = self.height

        return obj

    def restoreFromJson(self, js):
        self.width  = max(js['width'], self.editorWidth)
        self.height = max(js['height'], self.editorHeight)

        if 'basePrefab' in js:
            self.basePrefab = js['basePrefab']

        if 'floorHeight' in js:
            self.floorHeight = js['floorHeight']

        self._squares = list()
        for square in js['squares']:
            obj = self._sqareModel()
            obj.restoreFromJson(square)
            self._squares.append(obj)

    def saveMap(self, filename):
        extension = '.json'
        if not filename.endswith(extension):
            filename = filename + extension

        print("Saving map to " + filename)
        with open(filename, "w") as writeFile:
            json.dump(self.toSerializableObj(), writeFile, indent=4)

        self._setCurrentFile(filename)

    def openMap(self, filename):
        extension = '.json'
        if not filename.endswith(extension):
            filename = filename + extension

        print("Loading map from " + filename)

        with open(filename, "r") as readFile:
            jsObj = json.load(readFile)
            self.restoreFromJson(jsObj)

        self._setCurrentFile(filename)

        if self._updateCallback is not None:
            self._updateCallback()

    def currentFilePath(self):
        """Path this map was last opened from or saved to, or None if it has
        never been written (a freshly created map)."""
        return self._currentFilePath

    def isDirty(self):
        """True when the map differs from what is on disk.

        Deliberately compares content rather than tracking edits: the ~40
        mutating methods here (plus PropertiesPanel, which edits squares
        directly) have no single choke point, so a flag would need wiring at
        every one of them and would silently lie the moment one was missed.
        Hashing the serialized map costs ~5 ms on the largest real map, which
        is affordable at the 1 Hz the title bar polls it at."""
        return self._snapshot() != self._savedSnapshot

    def _snapshot(self):
        return hash(json.dumps(self.toSerializableObj(), sort_keys=True))

    def _setCurrentFile(self, filename):
        """Record the on-disk identity of the map after a successful open/save."""
        self._currentFilePath = filename
        self._savedSnapshot = self._snapshot()
        self.currentFileChanged.emit(filename)

    def updateEntireMap(self):
        self.updatedEntireMap.emit()

    def updateEntireMap(self):
        self.updatedEntireMap.emit()
        
    def setGroupProperty(self, selectionRange, modelFilter, property, value):
        for square in self._squares:
            if selectionRange.startCol <= square.x <= selectionRange.endCol and selectionRange.startRow <= square.y <= selectionRange.endRow and square.z == selectionRange.zLevel:
                if square.properties['model'] == modelFilter:
                    if property == 'additionalProperties':
                        for prop_name, prop_value in value.items():
                            square.setAdditioanalProperty(prop_name, prop_value)
                    else:
                        square.setProperty(property, value)
                    self.updateModelSize(square)

    def deleteGroupAdditionalProperty(self, selectionRange, modelFilter, names=None, clearAll=False):
        """Delete additional properties from every square of modelFilter in range.
        Pass names=[...] to drop those keys, or clearAll=True to remove all of them
        (resetting additionalProperties to empty). Returns the number of squares
        that actually lost at least one property."""
        affected = 0
        for square in self._squares:
            if selectionRange.startCol <= square.x <= selectionRange.endCol and selectionRange.startRow <= square.y <= selectionRange.endRow and square.z == selectionRange.zLevel:
                if square.properties['model'] == modelFilter:
                    if clearAll:
                        if square.clearAdditionalProperties():
                            affected += 1
                    else:
                        removed = False
                        for name in names or []:
                            if square.deleteAdditionalProperty(name):
                                removed = True
                        if removed:
                            affected += 1
        return affected

    def updateModelSize(self, square):
        model_name = square.getProperty('model')
        map_object = self._objCollection.getObject(model_name)
        if map_object:
            square.w = map_object.w
            square.h = map_object.h

    def overwriteEverythingWith(self, selectionRange, modelType):
        self.deleteObjectsInSelection(selectionRange)
        for row in range(selectionRange.startRow, selectionRange.endRow + 1):
            for col in range(selectionRange.startCol, selectionRange.endCol + 1):
                new_square = self.createObjectAt(col, row, selectionRange.zLevel)
                new_square.setModel(modelType)

        if self._updateCallback:
            self._updateCallback()

    # ----------------------------------------------------------------------- #
    # Edit engine: position-preserving fill, resize (insert/remove) and move.
    # These are the map operations the bwe_cli CLI used to implement inline; they
    # live here so the GUI and the CLI share one implementation and callers stop
    # reaching into _squares. Each ends with a single _updateCallback so the GUI
    # refreshes once (the CLI's callback is a no-op).
    # ----------------------------------------------------------------------- #

    def cloneSquare(self, serial, new_x=None, new_y=None):
        """Clone a serialized square into a fresh object with a NEW id (so a
        duplicated row/column does not collide with the source's ids).
        Preserves model, rotation, z, size and additionalProperties; overrides
        x/y if given."""
        data = dict(serial)
        data['id'] = ''  # empty id -> restoreFromJson mints a fresh uuid
        if new_x is not None:
            data['x'] = new_x
        if new_y is not None:
            data['y'] = new_y
        obj = self._sqareModel()
        obj.restoreFromJson(data)
        return obj

    def _fillOne(self, x, y, z, model_name, rotation=None):
        """Position-preserving fill of a single cell: reuse the square already
        at (x,y,z) - dropping any extra stacked layers - and set its
        model/rotation, or create one when the cell is empty."""
        existing = self.getSquareItems(x, y, z)
        if existing:
            keep = existing[0]
            for extra in existing[1:]:
                self.deleteSquareById(extra.id)
        else:
            keep = self.createObjectAt(x, y, z)
        keep.setModel(model_name)
        keep.setProperty('rotation', str(rotation) if rotation is not None else '0')
        self.updateModelSize(keep)

    def _fillRange(self, selectionRange, model_name, rotation=None):
        z = selectionRange.zLevel
        for y in range(selectionRange.startRow, selectionRange.endRow + 1):
            for x in range(selectionRange.startCol, selectionRange.endCol + 1):
                self._fillOne(x, y, z, model_name, rotation)

    def fillSelection(self, selectionRange, model_name, rotation=None):
        """Position-preserving fill of the whole selection: reuses the square
        already at each cell so unchanged cells produce a zero-byte diff. Use
        this to paint a base layer; use createObjectAt/place to stack a layer."""
        self._fillRange(selectionRange, model_name, rotation)
        if self._updateCallback:
            self._updateCallback()

    def fillBorder(self, selectionRange, model_name, width=1, rotation=None):
        """Draw a ring of one model around the selection (position-preserving)."""
        z = selectionRange.zLevel
        x = selectionRange.startCol
        y = selectionRange.startRow
        w = selectionRange.endCol - x + 1
        h = selectionRange.endRow - y + 1
        strips = [
            (x, y, w, width),                 # top
            (x, y + h - width, w, width),     # bottom
            (x, y, width, h),                 # left
            (x + w - width, y, width, h),     # right
        ]
        for (sx, sy, sw, sh) in strips:
            strip = SelectionRange(sx, sy, sx + sw - 1, sy + sh - 1, z)
            self._fillRange(strip, model_name, rotation)
        if self._updateCallback:
            self._updateCallback()

    def _insertRows(self, at, count, fill, copyFrom):
        src = None
        if copyFrom is not None:
            src = [sq.toSerializableObj() for sq in self._squares if sq.y == copyFrom]
        for sq in self._squares:
            if sq.y >= at:
                sq.y += count
        for i in range(count):
            new_y = at + i
            if src is not None:
                for serial in src:
                    self.addMapObject(self.cloneSquare(serial, new_y=new_y))
            elif fill is not None:
                for x in range(self.width):
                    self._fillOne(x, new_y, 0, fill)
            else:
                for x in range(self.width):
                    self.createEmpySquareAt(new_y, x)
        self.height += count

    def _insertCols(self, at, count, fill, copyFrom):
        src = None
        if copyFrom is not None:
            src = [sq.toSerializableObj() for sq in self._squares if sq.x == copyFrom]
        for sq in self._squares:
            if sq.x >= at:
                sq.x += count
        for i in range(count):
            new_x = at + i
            if src is not None:
                for serial in src:
                    self.addMapObject(self.cloneSquare(serial, new_x=new_x))
            elif fill is not None:
                for y in range(self.height):
                    self._fillOne(new_x, y, 0, fill)
            else:
                for y in range(self.height):
                    self.createEmpySquareAt(y, new_x)
        self.width += count

    def insertLine(self, axis, at, count=1, fill=None, copyFrom=None):
        """Insert `count` rows ('row') or columns ('col') before index `at`,
        shifting later lines to make room and renumbering coordinates. New cells
        are copied from line `copyFrom` (full-fidelity, all layers/z), filled
        with `fill` at z=0, or left as bare Empty squares."""
        if axis == 'row':
            self._insertRows(at, count, fill, copyFrom)
        else:
            self._insertCols(at, count, fill, copyFrom)
        if self._updateCallback:
            self._updateCallback()

    def _removeRows(self, at, count):
        end = at + count - 1
        self._squares[:] = [sq for sq in self._squares if not (at <= sq.y <= end)]
        for sq in self._squares:
            if sq.y > end:
                sq.y -= count
        self.height -= count

    def _removeCols(self, at, count):
        end = at + count - 1
        self._squares[:] = [sq for sq in self._squares if not (at <= sq.x <= end)]
        for sq in self._squares:
            if sq.x > end:
                sq.x -= count
        self.width -= count

    def removeLine(self, axis, at, count=1):
        """Delete `count` rows ('row') or columns ('col') starting at index
        `at` and shift the remaining lines to close the gap."""
        if axis == 'row':
            self._removeRows(at, count)
        else:
            self._removeCols(at, count)
        if self._updateCallback:
            self._updateCallback()

    def moveObject(self, src, dst, z=0, modelFilter=None, fillOld=None, clearNew=False):
        """Relocate the object(s) at cell `src` to cell `dst` at z-level `z`.
        Moves every layer at the source, or only `modelFilter` if given.
        `fillOld` backfills the vacated footprint (cells no longer covered);
        `clearNew` deletes other squares under the destination footprint.
        Raises ValueError on no-such-source or out-of-bounds destination.
        Returns {'count', 'names', 'footprint'} describing what moved."""
        fx, fy = src
        tx, ty = dst
        targets = [sq for sq in self._squares
                   if sq.x == fx and sq.y == fy and sq.z == z
                   and (modelFilter is None or sq.getModel() == modelFilter)]
        if not targets:
            what = ("model %s " % modelFilter) if modelFilter else ""
            raise ValueError("no %ssquare at (%d,%d,z=%d) to move" % (what, fx, fy, z))
        # Rotation-aware footprint: a rotated object occupies getSize() cells,
        # not its raw stored w/h. Bounds check, clearNew region and fillOld
        # backfill must all use the on-grid size or a rotated object bleeds.
        foot_w = max(sq.getSize().w for sq in targets)
        foot_h = max(sq.getSize().h for sq in targets)
        if tx < 0 or ty < 0 or tx + foot_w > self.width or ty + foot_h > self.height:
            raise ValueError("destination (%d,%d) + footprint %dx%d exceeds map %dx%d "
                             "(insert rows/cols first)"
                             % (tx, ty, foot_w, foot_h, self.width, self.height))
        dx, dy = tx - fx, ty - fy
        target_ids = {sq.id for sq in targets}
        if clearNew:
            ex, ey = tx + foot_w - 1, ty + foot_h - 1
            self._squares[:] = [sq for sq in self._squares
                if not (tx <= sq.x <= ex and ty <= sq.y <= ey and sq.z == z
                        and sq.id not in target_ids)]
        for sq in targets:
            sq.x += dx
            sq.y += dy
        if fillOld:
            old_cells = {(x, y) for x in range(fx, fx + foot_w) for y in range(fy, fy + foot_h)}
            new_cells = {(x, y) for x in range(tx, tx + foot_w) for y in range(ty, ty + foot_h)}
            for (x, y) in sorted(old_cells - new_cells):
                self._fillOne(x, y, z, fillOld)
        if self._updateCallback:
            self._updateCallback()
        return {
            'count': len(targets),
            'names': sorted({sq.getModel() for sq in targets}),
            'footprint': (foot_w, foot_h),
        }
