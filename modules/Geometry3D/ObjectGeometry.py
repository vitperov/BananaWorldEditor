# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Parses the optional "geometry" field of an object.json catalog entry.
# See PLAN-viewer.md for the schema and the decisions behind it.

import os
from typing import Dict, List, Optional

from modules.Geometry3D.Primitives import Box, Prism


class ObjectGeometry:
    TYPE_PRIMITIVES = 'primitives'
    TYPE_MESH = 'mesh'

    def __init__(self, geometryType: str,
                 parts: Optional[List[Box]] = None,
                 meshFile: Optional[str] = None):
        self.geometryType = geometryType
        self.parts = parts if parts is not None else []
        self.meshFile = meshFile

    def isPrimitives(self) -> bool:
        return self.geometryType == self.TYPE_PRIMITIVES

    def isMesh(self) -> bool:
        return self.geometryType == self.TYPE_MESH

    @classmethod
    def from_json(cls, json_data: Dict, base_path: str) -> 'ObjectGeometry':
        geometryType = json_data.get('type', '')

        if geometryType == cls.TYPE_PRIMITIVES:
            parts = []
            for part in json_data.get('parts', []):
                shape = part.get('shape', 'box')
                if shape == 'box':
                    parts.append(Box(origin=part['origin'],
                                     size=part['size'],
                                     textureSlot=part.get('textureSlot')))
                elif shape == 'prism':
                    parts.append(Prism(origin=part['origin'],
                                       size=part['size'],
                                       bottom=part['bottom'],
                                       top=part['top'],
                                       topCrease=part.get('topCrease'),
                                       bottomCrease=part.get('bottomCrease'),
                                       textureSlot=part.get('textureSlot')))
                else:
                    raise ValueError(f"Unsupported primitive shape: {shape}")
            return cls(geometryType, parts=parts)

        if geometryType == cls.TYPE_MESH:
            meshFile = os.path.join(base_path, json_data.get('file', ''))
            return cls(geometryType, meshFile=meshFile)

        raise ValueError(f"Unsupported geometry type: {geometryType}")
