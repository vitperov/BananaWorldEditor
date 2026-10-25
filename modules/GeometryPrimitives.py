# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from copy import copy
import math


class AreaSize():
    def __init__(self, w=0, h=0):
        self.w = w
        self.h = h
    
    def rotated(self, angle):
        angleRad = math.radians(angle)
        newW = int(round(abs(self.w * math.cos(angleRad) - self.h * math.sin(angleRad))))
        newH = int(round(abs(self.w * math.sin(angleRad) + self.h * math.cos(angleRad))))
        
        return AreaSize(newW, newH)

    def __repr__(self):
        return "(" + str(self.w) + ", " + str(self.h) + ")"

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, pt):
        # return new point to avoid references
        return Point(self.x + pt.x,
                     self.y + pt.y)

    def __iadd__(self, pt):
        self.x += pt.x
        self.y += pt.y
        return self

    def __sub__(self, pt):
        # return new point to avoid references
        return Point(self.x - pt.x,
                     self.y - pt.y)

    def __isub__(self, pt):
        self.x -= pt.x
        self.y -= pt.y
        return self

    def __eq__(self, other):
        return isinstance(other, Point) and self.x == other.x and self.y == other.y

    def __hash__(self):
        return hash((self.x, self.y))

    def __repr__(self):
        return "(" + str(self.x) + ", " + str(self.y) + ")"

class Rectangle:
    def __init__(self, pt, sz):
        self.pt = copy(pt)
        self.sz = copy(sz)
        
    def __repr__(self):
        return "[pt:" + str(self.pt) + ", sz:" + str(self.sz) + "]"
        
    def expand(self, value):
        return Rectangle(
            Point(self.pt.x - value,
                  self.pt.y - value),
            AreaSize(self.sz.w + 2 * value,
                     self.sz.h + 2 * value))
        
    def shrink(self, value):
        # TODO check null size
        return Rectangle(
            Point(self.pt.x + value,
                  self.pt.y + value),
            AreaSize(self.sz.w - 2 * value,
                     self.sz.h - 2 * value))
        
    def isRectInside(self, rect):
        return ((rect.pt.x >= self.pt.x) and
                (rect.pt.y >= self.pt.y) and
                (rect.pt.x + rect.sz.w <= self.pt.x + self.sz.w) and
                (rect.pt.y + rect.sz.h <= self.pt.y + self.sz.h) )
               
    def isRectPartiallyInside(self, rect):
        return (self.isPointInside(rect.pt) or
                self.isPointInside(Point(rect.pt.x + rect.sz.w, rect.pt.y + rect.sz.h)))
               
               
    def isPointInside(self, pt):
        return ((pt.x >= self.pt.x) and
                (pt.y >= self.pt.y) and
                (pt.x <= self.pt.x + self.sz.w) and
                (pt.y <= self.pt.y + self.sz.h) )
