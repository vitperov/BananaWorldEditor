# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
#
# Non-modal 3D view of a house map. Pure PyQt5 OpenGL (QOpenGLWidget +
# QOpenGLShaderProgram + QOpenGLTexture + QMatrix4x4), no extra
# dependencies. Boxes are textured from the texture catalog, tiled by
# world size (UVs come from Geometry3D.BoxFaces, shared with the
# exporters). Boxes whose texture is unset or missing from the catalog
# fall back to a flat color so the scene still renders.

import colorsys
import hashlib
import math
import struct

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QImage, QMatrix4x4, QOpenGLBuffer, QOpenGLShader,
                         QOpenGLShaderProgram, QOpenGLTexture,
                         QOpenGLVersionProfile, QVector3D)
from PyQt5.QtWidgets import QOpenGLWidget, QVBoxLayout, QWidget

from modules.Geometry3D.BoxFaces import partFaces

# OpenGL constants (PyQt5 exposes functions via versionFunctions(), the
# constants are mirrored here to avoid depending on its attribute set).
GL_DEPTH_TEST = 0x0B71
GL_COLOR_BUFFER_BIT = 0x4000
GL_DEPTH_BUFFER_BIT = 0x0100
GL_TRIANGLES = 0x0004
GL_FLOAT = 0x1406

FLOATS_PER_VERTEX = 8  # position(3) + normal(3) + uv(2)
STRIDE = FLOATS_PER_VERTEX * 4
VERTEX_ATTRIBUTES = (('position', 0, 3), ('normal', 12, 3), ('uv', 24, 2))

VERTEX_SHADER = """
attribute vec3 position;
attribute vec3 normal;
attribute vec2 uv;
uniform mat4 mvp;
varying vec3 vNormal;
varying vec2 vUV;
void main() {
    gl_Position = mvp * vec4(position, 1.0);
    vNormal = normal;
    vUV = uv;
}
"""

# One draw call per batch: a batch is either textured (sampler bound,
# useTexture = 1) or a flat color (useTexture = 0), both lit the same way.
FRAGMENT_SHADER = """
uniform sampler2D tex;
uniform int useTexture;
uniform vec3 color;
varying vec3 vNormal;
varying vec2 vUV;
void main() {
    vec3 base = useTexture != 0 ? texture2D(tex, vUV).rgb : color;
    vec3 lightDir = normalize(vec3(0.4, 0.25, 1.0));
    float diffuse = max(dot(normalize(vNormal), lightDir), 0.0);
    // Light both winding directions; no face culling is used.
    float back = max(dot(normalize(vNormal), -lightDir), 0.0);
    float light = 0.45 + 0.55 * max(diffuse, 0.3 * back);
    gl_FragColor = vec4(base * light, 1.0);
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


def boxTriangles(box):
    """Triangle vertices of one part: position, outward normal, world UV."""
    data = []
    for face in partFaces(box):
        for index in face.triangleIndices:
            data.extend(face.corners[index])
            data.extend(face.normal)
            data.extend(face.uvs[index])
    return data


class Batch:
    """A contiguous vertex range drawn with one texture (or one color).

    textureFile is None for flat-colored batches; color is the fallback
    used when textureFile is None or its image cannot be loaded.
    """

    def __init__(self, textureFile, color, first, count):
        self.textureFile = textureFile
        self.color = color
        self.first = first
        self.count = count


def buildBatches(boxes, textureFiles):
    """Group boxes by texture file / fallback color into draw batches.

    Returns (flat float list, batches). Boxes with no texture slot (the
    ground) take GROUND_COLOR; an unset texture property takes
    UNTEXTURED_COLOR; a texture name without a catalog image keeps the
    stable hash color so a missing texture stays recognizable.
    """
    groups = {}
    for box in boxes:
        if box.textureSlot is None:
            key = (None, GROUND_COLOR)
        else:
            key = (textureFiles.get(box.texture), colorForTexture(box.texture))
        groups.setdefault(key, []).append(box)

    data = []
    batches = []
    for (textureFile, color), groupBoxes in groups.items():
        first = len(data) // FLOATS_PER_VERTEX
        for box in groupBoxes:
            data.extend(boxTriangles(box))
        batches.append(Batch(textureFile, color, first,
                             len(data) // FLOATS_PER_VERTEX - first))
    return data, batches


def loadTexture(imageFile):
    """Create a tiling, mipmapped QOpenGLTexture from an image file.

    Needs a current GL context. Returns None when the image cannot be
    read, so the caller can fall back to a flat color.
    """
    image = QImage(imageFile)
    if image.isNull():
        return None
    # QImage rows run top-down, GL texture rows bottom-up; mirroring puts
    # the image's bottom row at v = 0, i.e. on the floor for wall faces.
    image = image.convertToFormat(QImage.Format_RGBA8888).mirrored()
    texture = QOpenGLTexture(image, QOpenGLTexture.GenerateMipMaps)
    texture.setWrapMode(QOpenGLTexture.Repeat)
    texture.setMinificationFilter(QOpenGLTexture.LinearMipMapLinear)
    texture.setMagnificationFilter(QOpenGLTexture.Linear)
    texture.setMaximumAnisotropy(8.0)
    return texture


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
        self._batches = []
        # Texture file -> QOpenGLTexture, created lazily inside paintGL
        # (the only place the context is guaranteed current). A file
        # that failed to load is cached as None so it is not retried on
        # every frame.
        self._textures = {}
        self._dirty = False
        self._aspect = 1.0

        # Orbit camera around a target point.
        self._target = QVector3D(0.0, 0.0, 0.0)
        self._distance = 20.0
        self._azimuthDeg = -135.0
        self._elevationDeg = 35.0
        self._lastMousePos = None

    def setScene(self, boxes, textureFiles):
        """Replace the scene: world boxes plus texture name -> image path."""
        data, self._batches = buildBatches(boxes, textureFiles)
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
        self._program.setUniformValue('tex', 0)
        for name, offset, size in VERTEX_ATTRIBUTES:
            self._program.enableAttributeArray(name)
            self._program.setAttributeBuffer(name, GL_FLOAT, offset, size, STRIDE)

        for batch in self._batches:
            texture = self._textureFor(batch.textureFile)
            if texture is not None:
                texture.bind(0)
                self._program.setUniformValue('useTexture', 1)
            else:
                self._program.setUniformValue('useTexture', 0)
                self._program.setUniformValue('color', QVector3D(*batch.color))
            self._gl.glDrawArrays(GL_TRIANGLES, batch.first, batch.count)
            if texture is not None:
                texture.release(0)

        for name, _, _ in VERTEX_ATTRIBUTES:
            self._program.disableAttributeArray(name)
        self._program.release()
        self._vbo.release()

    def _textureFor(self, imageFile):
        if imageFile is None:
            return None
        if imageFile not in self._textures:
            texture = loadTexture(imageFile)
            if texture is None:
                print(f"3D view: cannot load texture image {imageFile}")
            self._textures[imageFile] = texture
        return self._textures[imageFile]

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

    def setScene(self, scene):
        """Show a SceneBuilder.Scene (boxes + texture image paths)."""
        self._glWidget.setScene(scene.boxes, scene.textureFiles)
