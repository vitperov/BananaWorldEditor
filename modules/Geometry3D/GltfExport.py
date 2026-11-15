# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Exports catalog objects with primitive geometry as glTF 2.0 binaries
# (.glb), one file per object, plus the texture images and a manifest
# that ties them together. Pure Python (json + struct), no Qt and no
# third-party glTF library, so the CLI and the tests can use it too.
#
# What is exported (see PLAN-viewer.md, "No logic is exported"):
# - one mesh per object, with one primitive per texture slot. Primitive
#   i uses material i, and material i is named after the slot
#   ("externalTexture", ...). Textures are NOT baked into the mesh: the
#   engine loader fills the material slots from the map file's
#   additionalProperties at load time, so texture combinations never
#   become assets.
# - every catalog texture image, copied next to the meshes, so the
#   loader has something to put into the slots.
# - manifest.json: object -> file + slot order, texture -> file, units
#   and the axis convention.
#
# Coordinates: primitives are authored in editor space (x, y = grid
# plane as the 2D editor draws it, z up, meters). glTF is Y-up and
# right-handed; the conversion is the rotation (x, y, z) -> (x, z, -y)
# and happens only here. The mesh origin stays at the square's
# min-x/min-y corner, so placement in the engine is the translation
# (x * SQUARE_SIZE, y * SQUARE_SIZE, z * FLOOR_HEIGHT) in editor space,
# rotated around the square center — the same rule MapToPrimitives uses.

import json
import os
import shutil
import struct
from typing import Dict, List, Optional, Tuple

from modules.Geometry3D.BoxFaces import boxFaces, Face
from modules.Geometry3D.MapToPrimitives import SQUARE_SIZE, FLOOR_HEIGHT
from modules.Geometry3D.ObjectGeometry import ObjectGeometry

MANIFEST_NAME = 'manifest.json'
TEXTURES_DIR = 'textures'
MANIFEST_FORMAT = 1
GENERATOR = 'BananaWorldEditor'

GLB_MAGIC = 0x46546C67       # 'glTF'
GLB_VERSION = 2
CHUNK_JSON = 0x4E4F534A      # 'JSON'
CHUNK_BIN = 0x004E4942       # 'BIN\0'

COMPONENT_FLOAT = 5126
COMPONENT_UNSIGNED_SHORT = 5123
COMPONENT_UNSIGNED_INT = 5125
TARGET_ARRAY_BUFFER = 34962
TARGET_ELEMENT_ARRAY_BUFFER = 34963
MODE_TRIANGLES = 4


def toGltfPosition(point) -> Tuple[float, float, float]:
    """Editor space (x, y, z-up) -> glTF space (Y-up, right-handed).

    A -90 degree rotation about X: a proper rotation, so triangle
    winding and handedness are preserved. Works for normals as well.
    """
    x, y, z = point
    return (x + 0.0, z + 0.0, -y + 0.0)  # + 0.0 normalizes -0.0


def toGltfUV(uv) -> Tuple[float, float]:
    """Flip v: BoxFaces uses v = 0 at the image bottom (GL convention),
    glTF puts v = 0 at the image top."""
    u, v = uv
    return (u, 1.0 - v)


def slotOrder(geometry: ObjectGeometry) -> List[Optional[str]]:
    """Texture slots in order of first appearance in the part list.

    This is the material / primitive order of the exported mesh.
    """
    slots = []
    for part in geometry.parts:
        if part.textureSlot not in slots:
            slots.append(part.textureSlot)
    return slots


def _pad(data: bytes, alignment: int = 4, fill: bytes = b'\x00') -> bytes:
    remainder = len(data) % alignment
    return data if remainder == 0 else data + fill * (alignment - remainder)


class _BufferBuilder:
    """Accumulates the binary chunk and the bufferViews/accessors for it."""

    def __init__(self):
        self.data = bytearray()
        self.bufferViews = []
        self.accessors = []

    def addView(self, blob: bytes, target: int) -> int:
        while len(self.data) % 4:
            self.data.append(0)
        self.bufferViews.append({
            'buffer': 0,
            'byteOffset': len(self.data),
            'byteLength': len(blob),
            'target': target,
        })
        self.data.extend(blob)
        return len(self.bufferViews) - 1

    def addAccessor(self, view: int, componentType: int, count: int,
                    accessorType: str, minimum=None, maximum=None) -> int:
        accessor = {
            'bufferView': view,
            'componentType': componentType,
            'count': count,
            'type': accessorType,
        }
        if minimum is not None:
            accessor['min'] = minimum
            accessor['max'] = maximum
        self.accessors.append(accessor)
        return len(self.accessors) - 1


def _primitiveData(parts):
    """Flatten the boxes of one slot into glTF-space vertex arrays."""
    positions, normals, uvs, indices = [], [], [], []
    for box in parts:
        for face in boxFaces(box):
            base = len(positions)
            normal = toGltfPosition(face.normal)
            for corner, uv in zip(face.corners, face.uvs):
                positions.append(toGltfPosition(corner))
                normals.append(normal)
                uvs.append(toGltfUV(uv))
            indices.extend(base + i for i in Face.TRIANGLE_INDICES)
    return positions, normals, uvs, indices


def buildGltf(name: str, geometry: ObjectGeometry) -> Tuple[Dict, bytes]:
    """glTF JSON document and binary buffer for one object."""
    if not geometry.isPrimitives():
        raise ValueError(f"{name}: only primitive geometry can be exported")

    buffers = _BufferBuilder()
    primitives = []
    materials = []
    for materialIndex, slot in enumerate(slotOrder(geometry)):
        parts = [part for part in geometry.parts if part.textureSlot == slot]
        positions, normals, uvs, indices = _primitiveData(parts)

        def floatBlob(vectors):
            return struct.pack(f'<{len(vectors) * len(vectors[0])}f',
                               *[c for v in vectors for c in v])

        positionView = buffers.addView(floatBlob(positions), TARGET_ARRAY_BUFFER)
        normalView = buffers.addView(floatBlob(normals), TARGET_ARRAY_BUFFER)
        uvView = buffers.addView(floatBlob(uvs), TARGET_ARRAY_BUFFER)
        if len(positions) <= 0xFFFF:
            indexType, indexFormat = COMPONENT_UNSIGNED_SHORT, 'H'
        else:
            indexType, indexFormat = COMPONENT_UNSIGNED_INT, 'I'
        indexView = buffers.addView(struct.pack(f'<{len(indices)}{indexFormat}', *indices),
                                    TARGET_ELEMENT_ARRAY_BUFFER)

        minimum = [min(p[i] for p in positions) for i in range(3)]
        maximum = [max(p[i] for p in positions) for i in range(3)]
        primitives.append({
            'attributes': {
                'POSITION': buffers.addAccessor(positionView, COMPONENT_FLOAT,
                                                len(positions), 'VEC3', minimum, maximum),
                'NORMAL': buffers.addAccessor(normalView, COMPONENT_FLOAT,
                                              len(normals), 'VEC3'),
                'TEXCOORD_0': buffers.addAccessor(uvView, COMPONENT_FLOAT,
                                                  len(uvs), 'VEC2'),
            },
            'indices': buffers.addAccessor(indexView, indexType, len(indices), 'SCALAR'),
            'material': materialIndex,
            'mode': MODE_TRIANGLES,
        })
        # Neutral matte placeholder; the loader replaces baseColorTexture
        # per instance. Named after the slot so loaders can match by name
        # as well as by index.
        materials.append({
            'name': slot if slot is not None else 'untextured',
            'pbrMetallicRoughness': {
                'baseColorFactor': [1.0, 1.0, 1.0, 1.0],
                'metallicFactor': 0.0,
                'roughnessFactor': 1.0,
            },
        })

    document = {
        'asset': {'version': '2.0', 'generator': GENERATOR},
        'scene': 0,
        'scenes': [{'nodes': [0]}],
        'nodes': [{'mesh': 0, 'name': name}],
        'meshes': [{'name': name, 'primitives': primitives}],
        'materials': materials,
        'buffers': [{'byteLength': len(buffers.data)}],
        'bufferViews': buffers.bufferViews,
        'accessors': buffers.accessors,
    }
    return document, bytes(buffers.data)


def packGlb(document: Dict, binary: bytes) -> bytes:
    """Wrap a glTF document and its buffer into the .glb container."""
    jsonChunk = _pad(json.dumps(document, separators=(',', ':')).encode('utf-8'),
                     fill=b' ')
    binChunk = _pad(binary)
    totalLength = 12 + 8 + len(jsonChunk) + 8 + len(binChunk)
    return b''.join([
        struct.pack('<III', GLB_MAGIC, GLB_VERSION, totalLength),
        struct.pack('<II', len(jsonChunk), CHUNK_JSON), jsonChunk,
        struct.pack('<II', len(binChunk), CHUNK_BIN), binChunk,
    ])


def unpackGlb(blob: bytes) -> Tuple[Dict, bytes]:
    """Inverse of packGlb (used by tests and loaders written in Python)."""
    magic, version, length = struct.unpack_from('<III', blob, 0)
    if magic != GLB_MAGIC or version != GLB_VERSION or length != len(blob):
        raise ValueError("not a glTF 2.0 binary")
    jsonLength, jsonType = struct.unpack_from('<II', blob, 12)
    if jsonType != CHUNK_JSON:
        raise ValueError("first GLB chunk is not JSON")
    document = json.loads(blob[20:20 + jsonLength].decode('utf-8'))
    binOffset = 20 + jsonLength
    binLength, binType = struct.unpack_from('<II', blob, binOffset)
    if binType != CHUNK_BIN:
        raise ValueError("second GLB chunk is not BIN")
    return document, blob[binOffset + 8:binOffset + 8 + binLength]


def objectFileName(name: str) -> str:
    return f'{name}.glb'


def textureFileName(name: str, imageFile: str) -> str:
    extension = os.path.splitext(imageFile)[1] or '.png'
    return f'{TEXTURES_DIR}/{name}{extension}'


class ExportReport:
    def __init__(self):
        self.objects: List[str] = []      # exported object names
        self.skipped: List[str] = []      # objects with non-primitive geometry
        self.textures: List[str] = []     # exported texture names
        self.manifestPath: Optional[str] = None


def exportCatalog(objCollection, texturesCollection, outDir: str) -> ExportReport:
    """Write every object with primitive geometry, all textures and the
    manifest into outDir (created if missing). Objects without a
    geometry field are not exportable yet and are left out silently;
    objects with "mesh" geometry are reported as skipped."""
    report = ExportReport()
    os.makedirs(outDir, exist_ok=True)

    manifestObjects = {}
    for mapObject in sorted(objCollection.objects.values(), key=lambda o: o.name):
        geometry = mapObject.geometry
        if geometry is None:
            continue
        if not geometry.isPrimitives():
            report.skipped.append(mapObject.name)
            continue
        document, binary = buildGltf(mapObject.name, geometry)
        fileName = objectFileName(mapObject.name)
        with open(os.path.join(outDir, fileName), 'wb') as file:
            file.write(packGlb(document, binary))
        manifestObjects[mapObject.name] = {
            'file': fileName,
            'materialSlots': [slot if slot is not None else 'untextured'
                              for slot in slotOrder(geometry)],
            'footprint': [mapObject.w, mapObject.h],
        }
        report.objects.append(mapObject.name)

    manifestTextures = {}
    if texturesCollection is not None:
        os.makedirs(os.path.join(outDir, TEXTURES_DIR), exist_ok=True)
        for name in sorted(texturesCollection.allTextureTypes()):
            imageFile = texturesCollection.getTextureFile(name)
            if not imageFile or not os.path.isfile(imageFile):
                continue
            fileName = textureFileName(name, imageFile)
            shutil.copyfile(imageFile, os.path.join(outDir, fileName))
            manifestTextures[name] = fileName
            report.textures.append(name)

    manifest = {
        'format': MANIFEST_FORMAT,
        'generator': GENERATOR,
        'units': 'meters',
        'squareSize': SQUARE_SIZE,
        'floorHeight': FLOOR_HEIGHT,
        'axes': {
            'editor': 'x and y span the grid as the 2D editor draws it, z is up',
            'gltf': 'X = x, Y = z, Z = -y (rotation, winding preserved)',
            'origin': "the square's min-x/min-y corner; place at "
                      "(x * squareSize, y * squareSize, z * floorHeight) in "
                      "editor space, rotate around the footprint center",
        },
        'objects': manifestObjects,
        'textures': manifestTextures,
    }
    report.manifestPath = os.path.join(outDir, MANIFEST_NAME)
    with open(report.manifestPath, 'w') as file:
        json.dump(manifest, file, indent=4)
        file.write('\n')
    return report
