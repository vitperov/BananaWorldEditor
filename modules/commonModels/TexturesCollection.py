# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import os
import json
from typing import List, Dict

class TextureObject:
    def __init__(self, name: str, iconFile: str):
        self.name = name
        self.iconFile = iconFile

    @classmethod
    def from_json(cls, json_data: Dict, base_path: str):
        return cls(
            name=json_data.get('name', ''),
            iconFile=os.path.join(base_path, json_data.get('iconFile', '')),
        )

class TexturesCollection:
    def __init__(self, searchpaths: List[str]):
        self.searchpaths = searchpaths
        self.textures: Dict[str, TextureObject] = {}
        self._load_textures()

    def _load_textures(self):
        for searchpath in self.searchpaths:
            for root, dirs, files in os.walk(searchpath):
                if 'object.json' in files:
                    with open(os.path.join(root, 'object.json'), 'r') as file:
                        data = json.load(file)
                        texture_object = TextureObject.from_json(data, root)
                        self.textures[texture_object.name] = texture_object

    def allTextureTypes(self) -> List[str]:
        return list(self.textures.keys())

    def getIcon(self, texname: str) -> str:
        texture_object = self.textures.get(texname)
        if texture_object:
            return texture_object.iconFile
        else:
            return None
        
    def getTexture(self, texname: str) -> TextureObject:
        return self.textures.get(texname)
