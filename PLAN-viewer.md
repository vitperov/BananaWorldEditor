# Plan: Generated 3D objects and built-in viewer

Working plan for the "Generated 3D objects" and "Built-in 3D viewer"
items from ROADMAP.md. Decisions recorded here so the goal is not lost
between sessions.

## Goal

A Python 3D render view built into the editor, starting with the
simplest objects: walls and corners. The same geometry description
later feeds exporters for Unity, Godot and Unreal, so maps work out of
the box.

## Decisions

### Generate simple objects, import complex ones

Every catalog entry (`object.json`) gets an optional `geometry` field
with two possible forms:

- `"type": "primitives"` — the object is generated from simple
  textured primitives (boxes at first). Used for construction objects:
  wall, corner, window, door, floor.
- `"type": "mesh"` — the object is an imported mesh file (glTF).
  Used for complex objects: furniture, etc.

Both forms resolve to the same thing downstream: **a mesh plus named
texture slots**. The viewer, the exporter and the engine loaders
consume that unified description and never care which branch produced
it. Objects without a `geometry` field are simply not rendered /
exported yet.

### No logic is exported

The feared "script that changes textures based on properties" does not
exist as an exported asset. The pieces are:

- **Geometry**: one wall mesh, instanced N times.
- **Material assignment**: data, already stored in the map file
  (`additionalProperties.internalTexture` / `externalTexture`).
- **Loader**: a small piece of engine-side code, written once per
  engine by hand (not generated). It reads the map file, instantiates
  meshes at grid positions and fills material slots. It must exist
  anyway to place objects, so it carries the "logic" for free.

### Texture slots via submeshes — no combination explosion

The wall mesh has one submesh per texture slot (internal faces,
external faces). Engines expose a materials array on the renderer, one
slot per submesh. So:

- 3 textures → 3 materials, 1 wall mesh;
- a wall instance sets `materials[internal]` and `materials[external]`
  from map data at load time;
- texture combinations never become assets. 20 walls with 4
  internal/external combinations still export as 1 mesh + 3 textures.

### Export format: glTF, not FBX

FBX needs the Autodesk SDK or headless Blender; Unreal `.uasset` needs
an in-editor plugin. glTF is JSON + binary buffer, writable from pure
Python, and all three engines import it. One exporter + three thin
loaders instead of three exporters.

### UV rule: tile by world size

A wall spanning 3 squares tiles its texture 3×, it does not stretch
one copy. Face UVs are derived from world dimensions (1 texture repeat
per grid unit by default). This is part of the primitive format from
day one — retrofitting it after maps exist would be painful.

### Coordinates and units

- One 2D grid square = a 2 x 2 meter footprint; one floor = 3 meters
  high. Wall thickness 0.2 (two 0.1 slabs). Constants `SQUARE_SIZE`
  and `FLOOR_HEIGHT` live in `modules/Geometry3D/MapToPrimitives.py`.
- Primitives are authored in editor-native coordinates (x, y = grid
  plane as the 2D editor draws it, z = up), in meters. Conversion to
  each target convention (glTF is Y-up right-handed, Unity Y-up
  left-handed, Unreal Z-up left-handed) happens in the exporter, in
  exactly one place.
- **Reference point: the square's min-x/min-y corner**, not the
  center. World placement is then a pure translation
  (x * 2, y * 2, z * 3) matching the map file. Rotation happens
  around the footprint center, but only inside the converter.
- **Geometry may leave its square.** Walls straddle the grid line and
  roof eaves will overhang, so parts are not confined to 0..2. The
  only bound is `FOOTPRINT_MARGIN` (0.5 m, in `MapToPrimitives.py`), a
  sanity check on authored data — it catches a misplaced decimal
  point, it is not a design constraint.
- **Rotation matches the 2D editor**: the editor draws y downward and
  rotates icons clockwise on screen (QTransform().rotate()), so in map
  coordinates a 90-degree step is (dx, dy) -> (-dy, dx) around the
  square center. At rotation 0 the Wall runs along the y=0 edge
  (external face outward), the Corner is an L along the y=0 and x=0
  edges — same as the icons.
- **Corner joint: step, not 45-degree miter.** The legs butt into each
  other with a visible 0.1 end strip. A miter would need a wedge
  primitive (new shape, UVs, export) only to hide a seam that is
  nearly invisible anyway because both legs share the same external
  texture.

### Walls are centered on the grid line

A wall slab spans -0.1..+0.1 across its line, not 0..0.2 inside its
own square. This was changed after the first viewer test, and it is
the rule the exporters and the engine loaders must follow too.

Why, concretely — both problems come from the old "wall lives inside
its square" rule:

- **An internal wall showed its cross-section on the facade.** It ran
  the full 2 m of its square, so its end cap landed exactly on the
  outer surface of the perpendicular wall it met. Centered, the cap
  lands on that wall's center plane instead and is buried inside it.
- **An L of two walls depended on which square hosted each leg.** A
  grid line is shared by two squares, so there were four ways to build
  the same corner; three of them left a 0.2 m jog or a 0.2 x 0.2 x 3
  void, and the 2D editor drew all four identically. Centered, all
  four produce the same boxes. The host square now decides only which
  side is external — the one thing it should decide.

Costs, accepted: geometry leaves the square footprint by half a wall
thickness (see `FOOTPRINT_MARGIN` above); the house's outer surface
sits 0.1 m outside the grid rectangle, which roof overhangs must
account for; placing walls on the same line from *both* neighbouring
squares now yields two coincident slabs instead of a 0.4 m wall, which
is a map mistake worth flagging in validation later.

What centering does *not* fix: two walls meeting at 90 degrees cover
three of the four quadrants around the grid vertex and leave the
fourth — a 0.1 x 0.1 x 3 notch at the outside of the corner. No
placement avoids it; it is inherent to cell-length walls. See corner
fillers below.

### Corner fillers are placed by hand, not generated

The notch is filled by a small catalog object the user places
explicitly, in the square and rotation that put it at the right
vertex (rotation picks which of the square's four corners). Two
catalog entries, one `externalTexture` slot each:

- **`ThinPillar`** (flush): 0.1 x 0.1 x 3, exactly the missing quadrant, at square-
  local (-0.1, -0.1) at rotation 0. Invisible as a joint — the corner
  simply looks solid.
- **`Pillar`** (protruding): 0.2 x 0.2 x 3, centered on (-0.1, -0.1), i.e.
  spanning -0.2..0.0. It stands 0.1 m proud of both wall faces, which
  is what real house corners (quoins) look like, and it carries its
  own texture slot, so corners can be stone against plastered walls.

The offset placement matters: a 0.2 post centered on the grid *vertex*
instead would put its sides coplanar with the wall faces over a 0.1
strip and z-fight in every engine. Offset, every shared face is an
interface between two solids and is never visible.

The same object doubles as a free-standing stud or post — canopy
supports, shed corners, fence posts — hence the name `Pillar` rather
than anything corner-specific, and category `indoor,outdoor` so both the
house and the terrain editor offer it.

**Rejected: generating fillers automatically** from the wall network
(fill the uncovered quadrant wherever exactly two walls meet at 90
degrees). The rule is small and provably complete, but derived
geometry has no object to hang properties on, so per-corner texture
and size would need a parallel override mechanism, and the user loses
the ability to simply not have a post somewhere. Explicit objects keep
the map file the single source of truth: what the editor shows is what
every engine gets, with no junction logic to re-implement per engine.

The tedium of placing them is better solved by a generator plugin (see
below) than by hiding the geometry from the map.

### Ideas for later

- **A "fill corners" generator plugin.** `generators/` already hosts
  map-transforming plugins (`FixGrassUnderHouse` is the closest
  analogue). A plugin can walk the map, find every vertex where
  exactly two wall-type edges meet at 90 degrees, and insert a filler
  object into the map — real objects the user can then move, retexture
  or delete. This gives the convenience of autofill while keeping the
  map explicit, and it runs when the user asks instead of on every
  render.
- **Corner as a nested object.** Once the editor supports nested
  objects, `Corner` can be defined as a composition — two walls plus a
  corner filler — that is inserted and manipulated as one object. The
  corner then stops being a special primitive composition authored by
  hand in `object.json`: it is literally the same walls and filler the
  user would place themselves, so it cannot drift out of sync with
  them. The same mechanism would cover wall+door and wall+window
  corners as presets, and a porch, a bay window, a whole room template
  afterwards. Until then `Corner` stays as it is: a hand-authored L
  that fills its own quadrant, for the common all-plain-wall case.

## Geometry schema

One part = one box = one texture slot. No per-face texture mapping:
splitting a wall into an internal slab and an external slab is simpler
to author, solves the thin-sides question (each slab's edges take its
own texture), and costs nothing (see note below).

```json
"geometry": {
    "type": "primitives",
    "parts": [
        {
            "shape": "box",
            "origin": [0.0, -0.1, 0.0],
            "size": [2.0, 0.1, 3.0],
            "textureSlot": "externalTexture"
        },
        {
            "shape": "box",
            "origin": [0.0, 0.0, 0.0],
            "size": [2.0, 0.1, 3.0],
            "textureSlot": "internalTexture"
        }
    ]
}
```

- `origin`/`size` in meters, square-local (origin at the square's
  min-x/min-y corner, height 0..3); authored at rotation 0, the map's
  `rotation` (0/90/180/270) rotates the whole part list around the
  square center. Parts may stick out of the square — the wall above
  starts at y = -0.1 because walls are centered on the grid line.
- `textureSlot` names a slot from `additionalProperties`.
- Wall = 2 slabs (internal + external). Corner = 4 boxes
  (2 L-legs × internal/external slab), step-joined with no overlaps
  and no enclosed voids; the leg along y covers the outer corner
  quadrant so a plain Corner needs no filler.
- Window = the wall's two slabs cut into 4 pieces around a 1.2 x 1.2
  opening (sill 0.9, head 2.1) — the reveals take the slab textures —
  plus a frame (5 cm perimeter + cross, 6 cm deep, centered in the
  wall), an external casing (10 cm wide, 5 cm proud of the facade) and
  an internal windowsill (4 cm thick, 15 cm into the room). The sill
  board spans the whole square (x 0..2), not just the opening, so
  adjacent windows butt into one continuous sill; a short infill fills
  the opening between frame and internal face so there is no step.
  Where a window meets a perpendicular wall, the board end is buried in
  that wall — harmless and realistic.
  Slots: `internalTexture`, `externalTexture`, `frameTexture`,
  `casingTexture`, `sillTexture`. "Casing" over "trim" (generic: baseboards, corner
  boards) and "molding" (implies a profile boxes don't have) because it
  is the specific term for the trim around an opening, so the Door can
  reuse the slot name. No glass.
- `"type": "mesh"` form: `{"type": "mesh", "file": "Sofa.glb"}`.
- At export, all parts sharing a slot merge into one submesh / glTF
  primitive, so the mesh still has exactly one material slot per
  texture slot — same draw calls as per-face mapping would give.
- Later shapes (wedge, cylinder) can be added without changing the
  envelope.

**Cost note (mobile included):** a box is 12 triangles / 24 vertices;
two boxes are 24/48. What actually costs on mobile is draw calls, and
those are determined by material count, which is identical in both
approaches (one per texture slot). A whole 20-wall house is under a
thousand triangles either way — noise next to any character model.

## Tests: catalog-wide invariants only

No per-object expected-geometry tests (no hardcoded sofa coordinates
to maintain). Every test below iterates over *all* catalog objects
that declare geometry, so adding a new object changes zero test code —
the new object is validated automatically.

Implemented in `tests/test_geometry_invariants.py`
(`python3 -m unittest discover -s tests`, no Qt required).

Data validation (per object):
- every part's size components are > 0;
- every part stays near the object's footprint — within
  `FOOTPRINT_MARGIN` of (0..2w, 0..2h, 0..3). Parts are allowed
  outside it (centered walls, roof overhangs); the check only rejects
  grossly misplaced data;
- every `textureSlot` referenced by a part is declared in the
  object's `additionalProperties` (type `texture`);
- parts do not overlap each other (touching faces are fine).

Converter math (per object, the genuinely bug-prone part):
- rotating by 90° four times returns the original boxes;
- converting at rotation r equals converting at rotation 0 and then
  rotating the resulting boxes around the square center by r;
- converting a square placed at (x, y, z) equals converting at origin
  translated by (2x, 2y, 3z);
- part count and total volume are unchanged by rotation;
- rotated parts stay within the same margin of the footprint (square
  footprints only), i.e. rotation does not move geometry away from its
  square;
- texture slots resolve from additionalProperties; missing values
  resolve to None rather than failing.

No whole-house smoke test: it would only re-run the converter the
invariants already cover. The useful future version is map validation
(referenced models and texture names actually exist in the catalogs),
worth adding together with the glTF exporter.

## To investigate later

- **.glb vs .gltf / embedded vs external textures.** Both container
  forms can embed textures or reference external files. Embedding
  gives a single self-contained file, but it is unclear whether Unity
  (and the other engines) can apply per-platform texture settings
  (resolution downscaling, compression format) to textures living
  inside a glTF container — with separate PNG files this definitely
  works through the normal texture importer. Leaning toward external
  textures (meshes in .glb, textures as plain PNGs referenced by the
  manifest), but verify against Unity glTF importers (glTFast /
  UnityGLTF) before committing.
- **Material richness.** Start with the minimal glTF material subset:
  baseColorTexture only, metallic 0, roughness 1 (matte). Normal maps,
  roughness maps etc. can be added per-texture later without schema
  changes — a texture catalog entry would just grow optional extra
  maps.
- **glTF reader for the Python viewer** — needed only once the first
  `"type": "mesh"` object (furniture) appears; pick `trimesh` or
  `pygltflib` then.

## Current state

- **Geometry layer** (`modules/Geometry3D/`, Qt-free): `Primitives.py`
  (Box: rotate/translate/intersect), `ObjectGeometry.py` (parses the
  catalog `geometry` field), `MapToPrimitives.py` (map square →
  placed, rotated, texture-resolved world boxes; owns `SQUARE_SIZE`
  and `FLOOR_HEIGHT`, and `FOOTPRINT_MARGIN`). Wall and Corner carry
  geometry in their `object.json`, centered on the grid line, and so
  does Window;
  `Pillar` and `ThinPillar` are the hand-placed corner fillers.
  Invariant tests:
  `python3 -m unittest discover -s tests` (no Qt needed).
- **3D viewer** (`modules/Viewer3D/`): `SceneBuilder.py` turns a map
  model into boxes (skips objects without geometry, adds a thin ground
  slab); `Viewer3DWindow.py` is a non-modal window with a
  QOpenGLWidget renderer — pure PyQt5 (shader program, QMatrix4x4,
  versionFunctions), zero new dependencies. Orbit (left drag), pan
  (right drag), zoom (wheel); camera starts at 35° elevation fitted to
  the scene. Opened by the "3D" button in the house editor toolbar;
  each click rebuilds the scene from the current map. Boxes are
  flat-colored by resolved texture name (stable hash color; gray when
  the texture property is unset).

## Next steps

1. **Textures in the viewer.** QOpenGLTexture from the texture catalog
   images, UVs tiled by world size (the UV rule above).
2. **More construction objects.** Door, floor as multi-box
   compositions; terrain level.
3. **glTF export.** Serialize the same box lists to .glb meshes + a
   manifest; decide the texture embedding question (above).
4. **Engine loaders.** Unity first: map file + manifest + glTF → scene
   with material slots filled.
