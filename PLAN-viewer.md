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
  (x * 2, y * 2, z * 3) matching the map file, JSON coordinates stay
  non-negative, and the bounds check is simply 0..2. Rotation happens
  around the footprint center, but only inside the converter.
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

## Draft geometry schema (to refine during implementation)

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
            "origin": [0.0, 0.0, 0.0],
            "size": [2.0, 0.1, 3.0],
            "textureSlot": "externalTexture"
        },
        {
            "shape": "box",
            "origin": [0.0, 0.1, 0.0],
            "size": [2.0, 0.1, 3.0],
            "textureSlot": "internalTexture"
        }
    ]
}
```

- `origin`/`size` in meters, square-local (origin at the square's
  min-x/min-y corner, footprint spans 0..2, height 0..3); authored at
  rotation 0, the map's `rotation` (0/90/180/270) rotates the whole
  part list around the square center.
- `textureSlot` names a slot from `additionalProperties`.
- Wall = 2 slabs (internal + external). Corner = 4 boxes
  (2 L-legs × internal/external slab), step-joined with no overlaps
  and no enclosed voids.
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
- every part lies inside the object's footprint (0..2w, 0..2h, 0..3);
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
- rotated parts stay inside the footprint (square footprints only);
- texture slots resolve from additionalProperties; missing values
  resolve to None rather than failing.

No whole-house smoke test for now: without a load/render procedure it
would only re-run the converter the invariants already cover.
Revisit when the viewer exists — the useful future version is map
validation (referenced models and texture names actually exist in the
catalogs).

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

## Milestones

1. **Geometry support in the catalog.** *(done)* `geometry` parsing in
   `ObjectsCollection` (`modules/Geometry3D/ObjectGeometry.py`),
   primitive geometry for Wall and Corner in their `object.json`,
   converter `modules/Geometry3D/MapToPrimitives.py` (map square →
   placed, rotated, texture-resolved boxes), invariant tests in
   `tests/test_geometry_invariants.py`.
2. **Python 3D view.** QOpenGLWidget-based viewer (pure PyQt5: QOpenGL*
   classes + QMatrix4x4, zero new dependencies) with orbit/zoom
   camera, rendering the placed boxes — untextured first, then
   textures per face via QOpenGLTexture. Opened from the house editor.
3. **More construction objects.** Window, door, floor as multi-box
   compositions; terrain level.
4. **glTF export.** Serialize the same box lists to .glb meshes + a
   manifest; decide the texture embedding question (above).
5. **Engine loaders.** Unity first: map file + manifest + glTF → scene
   with material slots filled.
