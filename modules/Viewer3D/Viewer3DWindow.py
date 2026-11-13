# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Non-modal 3D view of a house map. Pure PyQt5 OpenGL (QOpenGLWidget +
# QOpenGLShaderProgram + QMatrix4x4), no extra dependencies. Boxes are
# flat-colored by their resolved texture name for now; real textures
# come later (see PLAN-viewer.md).

import colorsys
import hashlib
import math
import struct

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QMatrix4x4, QOpenGLBuffer, QOpenGLShader,
                         QOpenGLShaderProgram, QOpenGLVersionProfile,
                         QVector3D)
from PyQt5.QtWidgets import QOpenGLWidget, QVBoxLayout, QWidget

# OpenGL constants (PyQt5 exposes functions via versionFunctions(), the
# constants are mirrored here to avoid depending on its attribute set).
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_TRIANGLES = 0x0004
GL_FLOAT = 0x1406

FLOATS_PER_VERTEX = 9  # position(3) + normal(3) + color(3)
STRIDE = FLOATS_PER_VERTEX * 4

VERTEX_SHADER = """
attribute vec3 position;
attribute vec3 normal;
attribute vec3 color;
uniform mat4 mvp;
varying vec3 vNormal;
varying vec3 vColor;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    vNormal = normal;
    vColor = color;
}
"""

FRAGMENT_SHADER = """
varying vec3 vNormal;
varying vec3 vColor;
void main() {
    vec3 lightDir = normalize(vec3(0.4, 0.25, 1.0));
    float diffuse = max(dot(normalize(vNormal), lightDir), 0.0);
    // abs() lights both winding directions; no face culling is used.
    float back = max(dot(normalize(vNormal), -lightDir), 0.0);
    float light = 0.45 + 0.55 * max(diffuse, 0.3 * back);
    gl_FragColor = vec4(vColor * light, 1.0);
}
"""

GROUND_COLOR = (0.55, 0.6, 0.55)
UNTEXTURED_COLOR = (0.8, 0.8, 0.8)


def colorForTexture(textureName):
    """Stable, distinguishable flat color per texture name."""
    if not textureName:
        return UNTEXTURED_COLOR
    digest = hashlib.md5(textureName.encode('utf-8')).digest()
    hue = digest[0] / 255.0
    return colorsys.hls_to_rgb(hue, 0.6, 0.45)


def boxTriangles(box, color):
    """36 vertices (12 triangles) with outward normals and a flat color."""
    x0, y0, z0 = box.origin
    x1, y1, z1 = box.maxCorner()
    faces = [
        # (normal, four corners counter-clockwise seen from outside)
        ((-1, 0, 0), [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)]),
        ((+1, 0, 0), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]),
        ((0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
        ((0, +1, 0), [(x0, y1, z0), (x0, y1, z1), (x1, y1, z1), (x1, y1, z0)]),
        ((0, 0, -1), [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)]),
        ((0, 0, +1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
    ]
    data = []
    for normal, corners in faces:
        for index in (0, 1, 2, 0, 2, 3):
            data.extend(corners[index])
            data.extend(normal)
            data.extend(color)
    return data


class HouseGLWidget(QOpenGLWidget):
    """Renders a list of Geometry3D boxes with an orbit camera.

    Controls: left-drag orbits, right-drag pans, wheel zooms.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._gl = None
        self._program = None
        self._vbo = None
        self._vertexData = b''
        self._vertexCount = 0
        self._dirty = False
        self._aspect = 1.0

        # Orbit camera around a target point.
        self._target = QVector3D(0.0, 0.0, 0.0)
        self._distance = 20.0
        self._azimuthDeg = -135.0
        self._elevationDeg = 35.0
        self._lastMousePos = None

    def setBoxes(self, boxes):
        data = []
        for box in boxes:
            if box.textureSlot is None:
                color = GROUND_COLOR
            else:
                color = colorForTexture(box.texture)
            data.extend(boxTriangles(box, color))
        self._vertexCount = len(data) // FLOATS_PER_VERTEX
        self._vertexData = struct.pack(f'{len(data)}f', *data)
        self._dirty = True
        self._fitCamera(boxes)
        self.update()

    def _fitCamera(self, boxes):
        if not boxes:
            return
        minC = [min(b.origin[i] for b in boxes) for i in range(3)]
        maxC = [max(b.maxCorner()[i] for b in boxes) for i in range(3)]
        center = [(minC[i] + maxC[i]) / 2.0 for i in range(3)]
        radius = max(maxC[i] - minC[i] for i in range(3)) / 2.0
        self._target = QVector3D(*center)
        self._distance = max(radius * 2.5, 5.0)

    # --- OpenGL plumbing ---------------------------------------------------

    def initializeGL(self):
        profile = QOpenGLVersionProfile()
        profile.setVersion(2, 0)
        try:
            self._gl = self.context().versionFunctions(profile)
            self._gl.initializeOpenGLFunctions()
        except Exception as error:  # no matching PyQt5 GL bindings
            print(f"3D view unavailable: {error}")
            self._gl = None
            return

        self._gl.glClearColor(0.9, 0.93, 0.97, 1.0)
        self._gl.glEnable(GL_DEPTH_TEST)

        self._program = QOpenGLShaderProgram(self)
        self._program.addShaderFromSourceCode(QOpenGLShader.Vertex, VERTEX_SHADER)
        self._program.addShaderFromSourceCode(QOpenGLShader.Fragment, FRAGMENT_SHADER)
        self._program.link()

        self._vbo = QOpenGLBuffer(QOpenGLBuffer.VertexBuffer)
        self._vbo.create()

    def resizeGL(self, width, height):
        self._aspect = width / max(height, 1)

    def paintGL(self):
        if self._gl is None:
            return
        self._gl.glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self._vertexCount == 0:
            return

        self._vbo.bind()
        if self._dirty:
            self._vbo.allocate(self._vertexData, len(self._vertexData))
            self._dirty = False

        self._program.bind()
        self._program.setUniformValue('mvp', self._mvpMatrix())
        for name, offset in (('position', 0), ('normal', 12), ('color', 24)):
            self._program.enableAttributeArray(name)
            self._program.setAttributeBuffer(name, GL_FLOAT, offset, 3, STRIDE)

        self._gl.glDrawArrays(GL_TRIANGLES, 0, self._vertexCount)

        for name in ('position', 'normal', 'color'):
            self._program.disableAttributeArray(name)
        self._program.release()
        self._vbo.release()

    def _cameraEye(self):
        azimuth = math.radians(self._azimuthDeg)
        elevation = math.radians(self._elevationDeg)
        direction = QVector3D(math.cos(elevation) * math.cos(azimuth),
                              math.cos(elevation) * math.sin(azimuth),
                              math.sin(elevation))
        return self._target + direction * self._distance

    def _mvpMatrix(self):
        projection = QMatrix4x4()
        projection.perspective(45.0, self._aspect, 0.1, self._distance * 20.0)
        view = QMatrix4x4()
        view.lookAt(self._cameraEye(), self._target, QVector3D(0.0, 0.0, 1.0))
        return projection * view

    # --- Mouse controls ----------------------------------------------------

    def mousePressEvent(self, event):
        self._lastMousePos = event.pos()

    def mouseMoveEvent(self, event):
        if self._lastMousePos is None:
            return
        delta = event.pos() - self._lastMousePos
        self._lastMousePos = event.pos()

        if event.buttons() & Qt.LeftButton:
            self._azimuthDeg -= delta.x() * 0.4
            self._elevationDeg = min(89.0, max(-89.0,
                                               self._elevationDeg + delta.y() * 0.4))
        elif event.buttons() & Qt.RightButton:
            eye = self._cameraEye()
            forward = (self._target - eye).normalized()
            right = QVector3D.crossProduct(forward, QVector3D(0, 0, 1)).normalized()
            up = QVector3D.crossProduct(right, forward)
            panScale = self._distance * 0.002
            self._target += (-right * delta.x() + up * delta.y()) * panScale
        else:
            return
        self.update()

    def mouseReleaseEvent(self, event):
        self._lastMousePos = None

    def wheelEvent(self, event):
        steps = event.angleDelta().y() / 120.0
        self._distance = min(1000.0, max(1.0, self._distance * (0.9 ** steps)))
        self.update()


class Viewer3DWindow(QWidget):
    """Top-level, non-modal 3D view window."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle('BananaWorldEditor — 3D View')
        self.resize(900, 700)

        self._glWidget = HouseGLWidget(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._glWidget)
        self.setLayout(layout)

    def setBoxes(self, boxes):
        self._glWidget.setBoxes(boxes)
