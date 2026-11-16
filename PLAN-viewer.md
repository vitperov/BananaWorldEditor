# Plan: Generated 3D objects, built-in viewer, export

Covers the "Generated 3D objects" and "Built-in 3D viewer" items from
ROADMAP.md. Rules and decisions live here so they are not lost between
sessions. Finished work is described only as far as the rules it set.

## Goal

The editor builds 3D objects from simple boxes, shows them in its own
3D view, and exports them so a Unity, Godot or Unreal project can load
a map with no extra modelling work.

## How an object is described

Every catalog entry (`object.json`) may have a `geometry` field:

- `"type": "primitives"`: the object is a list of textured boxes.
  Used for construction objects (walls, corners, windows, doors, floors).
- `"type": "mesh"`: the object is a ready mesh file (glTF). Meant for
  furniture. No such object exists yet.

Both end up as the same thing: a mesh with named texture slots. Viewer,
exporter and engine loaders only see that. Objects without `geometry`
are not shown in 3D and not exported.

## Textures

- A texture slot is a texture-type entry in the object's
  `additionalProperties` (for example `externalTexture`). The map file
  stores which texture each placed object uses in each slot.
- A mesh has one submesh (one material) per texture slot. Textures are
  never baked into meshes. 20 walls with 4 texture combinations are
  still 1 mesh and the textures.
- The engine loader (hand-written once per engine, not generated) reads
  the map, places meshes and fills the material slots. Nothing else is
  exported as "logic".
- Texture catalog entry (`textures/<name>/object.json`): `iconFile` is
  the small picker picture; optional `textureFile` is the full-size
  tileable image. Without `textureFile`, the icon is used as the texture.
- Textures tile by world size: one repeat per grid square (2 m). A 3 m
  high wall shows 1.5 repeats, never one stretched copy. UVs are
  computed from world position, so neighbouring walls continue the
  pattern without seams, bricks stay horizontal, the image bottom sits
  on the floor, and no face is mirrored. One shared module
  (`modules/Geometry3D/BoxFaces.py`) does this for viewer and export.

## Coordinates and units

- One grid square is 2 x 2 m. One floor is 3 m. A wall is 0.2 m thick
  (two 0.1 m slabs). Constants: `SQUARE_SIZE`, `FLOOR_HEIGHT` in
  `modules/Geometry3D/MapToPrimitives.py`.
- Boxes are authored in editor space: x and y as the 2D editor draws
  them, z up, meters. Each export target converts in exactly one
  function (glTF: `(x, y, z) -> (x, z, -y)`).
- The object origin is the square's min-x/min-y corner. World position
  is `(x * 2, y * 2, z * 3)`. Rotation turns the box list around the
  square center and matches the 2D editor: a 90-degree step is
  `(dx, dy) -> (-dy, dx)`.
- Boxes may stick out of their square (centered walls, future roof
  overhangs). `FOOTPRINT_MARGIN` (0.5 m) only catches gross data errors.

## Wall rules

- Walls are centered on the grid line: a slab spans -0.1..+0.1 across
  the line. Reason: wall ends are then hidden inside the walls they
  meet, and a corner looks the same whichever of the two neighbouring
  squares hosts each wall. The host square only decides which side is
  external.
- Consequence: the house's outer surface is 0.1 m outside the grid
  rectangle. Roof overhangs must allow for it. Two walls on the same
  line from both neighbouring squares produce two coincident slabs,
  which is a map error worth a validation warning later.
- Two walls meeting at 90 degrees leave a 0.1 x 0.1 notch on the
  outside of the corner. It is filled by hand-placed objects, not
  generated: `ThinPillar` (0.1 x 0.1, flush) or `Pillar` (0.2 x 0.2,
  stands 0.1 m proud, own texture slot). Both also serve as free
  standing posts. Generated fillers were rejected because they would
  have no object to carry a texture or to be deleted, and every engine
  would have to repeat the rule.
- Corner legs butt into each other (step joint). No 45-degree miter:
  it would need a new wedge shape to hide a seam that is barely visible.

## Geometry schema

One part is one box with one texture slot. No per-face textures.

```json
"geometry": {
    "type": "primitives",
    "parts": [
        {"shape": "box", "origin": [0.0, -0.1, 0.0], "size": [2.0, 0.1, 3.0], "textureSlot": "externalTexture"},
        {"shape": "box", "origin": [0.0, 0.0, 0.0], "size": [2.0, 0.1, 3.0], "textureSlot": "internalTexture"}
    ]
}
```

- `origin` and `size` in meters, relative to the square corner, authored
  at rotation 0.
- Wall: 2 slabs. Corner: 4 boxes (two L-legs, each with both slabs).
- Window: the two slabs cut around a 1.2 x 1.2 opening (sill at 0.9,
  head at 2.1), a frame that spans the whole wall thickness (so no
  wall texture shows in the reveal) with a thin cross flush with its
  external face, an external casing and an internal windowsill that
  spans the whole square so neighbouring windows share one sill.
  Slots: `internalTexture`, `externalTexture`, `frameTexture`,
  `casingTexture`, `sillTexture`. No glass.
- Door: the two slabs cut around a 1.0 x 2.1 opening, a frame that
  spans the whole wall thickness (so no wall texture shows in the
  reveal), a closed leaf, a casing on each side and one rectangular
  knob box on each side. Slots: `internalTexture`, `externalTexture`,
  `doorTexture` (leaf and frame), `casingTexture` (outside),
  `internalCasingTexture`, `knobTexture`. The leaf is always drawn
  closed; `doorState` is for the game, not for the geometry.
- Floor: two 0.05 m slabs (half the wall thickness in total) meeting
  at z = 0: the upper one keeps the pre-geometry `internalTexture`
  slot so existing maps stay valid, the lower one is the ceiling of
  the floor below (`ceilingTexture`).
- Mesh form: `{"type": "mesh", "file": "Sofa.glb"}`.
- Second shape, "prism" (same envelope: origin + size = bounding
  box): vertical prism over the footprint; "bottom" and "top" give a
  height per footprint corner in the cyclic order (x0,y0), (x1,y0),
  (x1,y1), (x0,y1), 0 <= bottom <= top <= size z. Spells box, roof
  wedge, hip/valley corner and sloped slab (examples in
  Primitives.Prism). Roofs: two thin sloped slabs with separate
  tiles/ceiling texture slots, like walls.
  - A non-planar bottom/top splits into two triangles along a
    diagonal. Default: the crease bulges outward (ridges, hips);
    "topCrease"/"bottomCrease" ("02" or "13") force the other
    diagonal for concave surfaces (roof valleys).
  - Side faces are always vertical; where bottom meets top they
    degenerate to a triangle or vanish (a wedge's eave edge).
  - Sloped faces tile with u horizontal along the eave and v up the
    slope by surface distance, so courses stay level and continue
    across squares (BoxFaces.faceTangents).
  - Part overlap checks use bounding boxes, so sloped parts still
    must not share bounding-box volume within one object.
- Cost is not a concern: a whole house is under a thousand triangles,
  and draw calls depend on the number of texture slots, not boxes.

## Export

- Format: glTF 2.0 binary (`.glb`), written in pure Python. FBX and
  Unreal's native format need external tools; glTF needs none and all
  three engines import it.
- The "Export 3d objects" button on the main screen asks for a
  directory and writes: one `.glb` per object with geometry (one
  primitive and one material per slot, material named after the slot,
  plain white placeholder), all texture images under `textures/`, and
  `manifest.json` (object files, slot order, footprints, texture files,
  units, axis convention).
- Textures are separate files, not embedded, so engines can apply their
  own per-platform texture settings. To confirm against Unity's glTF
  importers before loaders are written.
- Materials start minimal: base color only, matte. Normal or roughness
  maps can be added per texture later without changing the schema.

## Tests

Tests check rules over every catalog object instead of pinning any
object's coordinates, so a new object is tested automatically:

- `tests/test_geometry_invariants.py`: sizes positive, parts near the
  footprint, slots declared, no overlaps, rotation and placement math.
- `tests/test_box_faces.py`: the texture tiling rules.
- `tests/test_gltf_export.py`: exported files are well formed and match
  the parts.

Run: `python3 -m unittest discover -s tests` (no Qt needed).

## Where things are

- `modules/Geometry3D/`: Qt-free geometry layer (boxes, catalog
  parsing, map square to world boxes, faces and UVs, glTF export).
- `modules/Viewer3D/`: scene builder and the OpenGL window. Opened by
  the "3D" button in the house editor; the scene is rebuilt on each
  click. Orbit with left drag, pan with right drag, zoom with wheel.
  Unset texture: light gray. Unknown texture name: a fixed color per
  name, so a missing texture is visible.

## Open questions

- Full-size textures: built-in textures only have the 171 px icon. When
  more textures are added, decide the standard resolution and whether
  icons are generated from the textures.
- glTF reader for the viewer: needed once the first `"type": "mesh"`
  object appears. Candidates: `trimesh`, `pygltflib`.
- Map validation: warn about texture names and models that are not in
  the catalogs, and about doubled walls.

## Ideas for later

- "Fill corners" generator plugin: finds every 90-degree wall meeting
  and inserts a filler object into the map. Keeps the map explicit,
  removes the manual tedium.
- Corner as a nested object (two walls plus a filler) once the editor
  supports nested objects. Same mechanism for wall+door and wall+window
  presets, then porches and room templates.

## Next steps

1. More construction objects: terrain objects.
2. Engine loaders, Unity first: map file + manifest + glTF files to a
   scene with filled material slots. Settle embedded vs. external
   textures at the same time.
3. CLI command `bwe_cli.py export-3d <dir>` for build pipelines.
