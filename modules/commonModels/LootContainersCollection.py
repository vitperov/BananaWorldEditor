# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
import os
import json
from typing import List, Dict

class LootContainersCollection:
    def __init__(self, searchpaths: List[str]):
        self.searchpaths = searchpaths
        self.containers: List[str] = []
        self._load_containers()

    def _load_containers(self):
        for searchpath in self.searchpaths:
            if not os.path.isdir(searchpath):
                continue
            for root, dirs, files in os.walk(searchpath):
                if 'object.json' in files:
                    with open(os.path.join(root, 'object.json'), 'r') as file:
                        data = json.load(file)
                        name = data.get('name', '')
                        if name and name not in self.containers:
                            self.containers.append(name)

    def allContainerTypes(self) -> List[str]:
        return list(self.containers)
