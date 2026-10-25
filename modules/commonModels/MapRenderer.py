"""Render a map model as an ASCII grid.

Read-only view over a MapModelGeneral: turns the squares into one glyph per
cell (with a legend) so a map can be *seen* rather than read as a list of
records. Used by the ttmap CLI's `render` command; returns pure data
(rows + legend) so any front-end can format it.
"""


class MapRenderer:
    # Draw priority when several layers share a cell: base ground (0) is covered
    # by a surface such as a road (1), which is covered by any placed
    # structure/object (2). This keeps roads visible over grass while
    # walls/doors/furniture/houses show over the floor they sit on.
    GROUND = {'Grass', 'Empty', 'Floor'}
    SURFACE = {'Road'}

    # Stable, mnemonic glyphs for the most common models; everything else is
    # auto-assigned. Kept uppercase so footprint-continuation cells (lowercase)
    # never collide with an origin glyph.
    FIXED_GLYPHS = {'Grass': '.', 'Empty': ' ', 'Forest': 'F', 'Road': '#'}
    GLYPH_POOL = "ABCDEGHIJKLMNOPQRSTUVWXYZ0123456789@$%&*+=?"

    def __init__(self, model):
        self._model = model

    def _tier(self, model_name):
        if model_name in self.GROUND:
            return 0
        if model_name in self.SURFACE:
            return 1
        return 2

    def _assignGlyphs(self, models):
        """Give every distinct model a unique uppercase glyph. Prefer the
        model's own first alphanumeric character (so R=Road, W=Wall) and fall
        back to a shared pool on collision. Lowercase is reserved for
        footprints."""
        glyphs = {}
        used = set()
        for name, ch in self.FIXED_GLYPHS.items():
            if name in models:
                glyphs[name] = ch
                used.add(ch)
        for m in models:
            if m in glyphs:
                continue
            chosen = None
            for ch in m:
                up = ch.upper()
                if up.isalnum() and up not in used:
                    chosen = up
                    break
            if chosen is None:
                for ch in self.GLYPH_POOL:
                    if ch not in used:
                        chosen = ch
                        break
            glyphs[m] = chosen or '?'
            used.add(glyphs[m])
        return glyphs

    def render(self, z=None, rect=None):
        """Build the grid. `z` limits to one z-level (else topmost layer per
        cell is shown); `rect` is [x, y, w, h] limiting the drawn area.
        Returns {'rows': [str], 'legend': [{'model', 'glyph'}], 'rect': [x,y,w,h]}."""
        W, H = self._model.width, self._model.height
        if rect is not None:
            rx, ry, rw, rh = rect
        else:
            rx, ry, rw, rh = 0, 0, W, H
        x_end, y_end = rx + rw, ry + rh

        # For each visible cell keep the single most significant layer. Priority:
        # higher z, then draw-tier (ground < surface < object), then a
        # multi-cell object's own origin, then later array order (drawn on top).
        best = {}  # (cx, cy) -> (sortkey, model_name, is_footprint_continuation)
        for idx, sq in enumerate(self._model.getSquares()):
            if z is not None and sq.z != z:
                continue
            m = sq.getModel()
            # Use the rotation-aware footprint: a 4x7 object rotated 90 covers
            # 7x4 cells on the grid. Reading sq.w/sq.h raw would draw the
            # unrotated block (bleeding across neighbours).
            size = sq.getSize()
            fw, fh = size.w, size.h
            multicell = fw > 1 or fh > 1
            tier = self._tier(m)
            for dy in range(fh):
                for dx in range(fw):
                    cx, cy = sq.x + dx, sq.y + dy
                    if not (rx <= cx < x_end and ry <= cy < y_end):
                        continue
                    is_origin = dx == 0 and dy == 0
                    key = (sq.z, tier, 1 if (is_origin and multicell) else 0, idx)
                    prev = best.get((cx, cy))
                    if prev is None or key > prev[0]:
                        best[(cx, cy)] = (key, m, multicell and not is_origin)

        used_models = sorted({v[1] for v in best.values()})
        glyphs = self._assignGlyphs(used_models)

        def cell_glyph(cx, cy):
            entry = best.get((cx, cy))
            if entry is None:
                return ' '
            _key, m, is_footprint = entry
            g = glyphs[m]
            return g.lower() if is_footprint else g

        rows = []
        for cy in range(ry, y_end):
            rows.append("".join(cell_glyph(cx, cy) for cx in range(rx, x_end)))

        legend = [{'model': m, 'glyph': glyphs[m]} for m in used_models]
        return {'rows': rows, 'legend': legend, 'rect': [rx, ry, rw, rh]}
