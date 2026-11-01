# Roadmap

Future plans for BananaWorldEditor.

Project is not finished. Interfaces and file format can change.

## Generated 3D objects

Today the editor outputs a map file with arranged objects, but not the
objects themselves. The game builder has to provide the 3D assets
separately and wire them up, which takes a lot of effort.

An object catalog entry holds metadata only. Geometry is entirely on
the game builder's side. The plan is to describe objects as
compositions of simple primitives with their coordinates, painted with
textures. For example, a wall is one parallelepiped, a wall with a
window is several parallelepipeds, and so on. From such descriptions
the editor can generate ready-made 3D objects for Unity, Godot and
Unreal Engine. Maps then work out of the box:

- a default bundle of generated 3D objects comes with the map;
- the game builder can still provide their own 3D object;
- or just use a default object with a new custom texture.

## One editor with nested objects

The current division into terrain and house editors is artificial.
They are practically the same thing and differ only in size and the
objects placed. Refactor them into a single editor that treats a map
as nested objects:

- a house is an object placed inside a terrain;
- an area can be placed on the map and hold several houses;
- separate rooms can live inside a house;
- no hard limit on the number of nesting levels.

## Nested object updates

A change to a nested object must be seen by the editor one level up.
Today this does not work: the terrain editor places a house from a
standalone placeholder instead of reading the real house properties.
If you enlarge the house, the terrain still inserts the old size. The
parent editor should read the properties of the nested object, so the
next insert uses the new size.

## Built-in 3D viewer

The 2D editor is good and saves time when building scenes. But to see
how the scene actually looks we need a built-in 3D viewer.

- Near term: build a small viewer binary in Unity/Godot/Unreal that
  loads the engine objects and is called from Python.
- Long term: once the editor generates its own 3D objects from
  primitives (see above), render its own format directly, with no
  dependency on game engines.

## Format conversion helpers

Map versioning already exists. To start using it we need conversion
helpers: rename an old field to a new one, rename an old object type
to a new one, and so on.
