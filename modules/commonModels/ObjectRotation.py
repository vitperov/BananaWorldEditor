# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from enum import Enum

class ObjectRotation(str, Enum):
    deg0    = '0'
    deg90   = '90'
    deg180  = '180'
    deg270  = '270'
