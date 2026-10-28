#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
"""bwe_screenshot - save a screenshot of the editor window for a given map.

Launches the real GUI editor offscreen (no display needed), loads the given
map JSON in the chosen tab and saves a capture of the full editor window
(toolbar, map canvas, properties panel) - the picture the README doc
examples show. The map file is only read, never modified.

Invocation (from the Unity project root, via the symlink):
    python3 Assets/TtMapsEditor/bwe_screenshot.py <map.json> [--tab house|terrain] [--out <file>]

The image format is inferred from the --out extension (jpg, png, ...); the
doc pictures are written as JPEG with quality 90. One summary line (output
path + pixel dimensions) goes to stdout; library chatter goes to stderr.
"""

import argparse
import contextlib
import os
import sys

# Headless only: must be forced before any Qt import (no display, no Xvfb).
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Original working directory: the map argument (and an explicit --out) are
# resolved against this BEFORE we chdir into the editor root below.
ORIG_CWD = os.getcwd()

# Real editor root (resolve symlinks so relative paths - resources, mapObjects,
# the doc/ defaults - point at the true repo).
EDITOR_ROOT = os.path.dirname(os.path.realpath(__file__))

# Default --out per tab, relative to the editor root (the doc pictures live
# there); an explicit --out resolves against the invocation cwd.
DEFAULT_OUT = {
    'house': 'doc/houseExample.jpg',
    'terrain': 'doc/terrainExample.jpg',
}

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
JPEG_QUALITY = 90


@contextlib.contextmanager
def _stdout_to_stderr():
    """Redirect library chatter (print statements in the model, the plugin
    loaders and the widget code) to stderr so stdout carries only the summary
    line."""
    old = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bwe_screenshot",
        description="Save a screenshot of the editor window for a map.")
    parser.add_argument("map", help="path to the map JSON file")
    parser.add_argument("--tab", choices=("house", "terrain"), default="house",
                        help="which editor tab to open (default: house)")
    parser.add_argument("--out", default=None,
                        help="image file to write (default: %s for house, %s for "
                             "terrain; format inferred from the extension)"
                             % (DEFAULT_OUT['house'], DEFAULT_OUT['terrain']))
    return parser


def _supported_formats():
    from PyQt5.QtGui import QImageWriter
    return {bytes(f).decode('ascii').lower()
            for f in QImageWriter.supportedImageFormats()}


def main(argv=None):
    args = build_parser().parse_args(argv)

    # The map argument and an explicit --out resolve against the invocation
    # cwd; only the default --out paths are editor-root-relative.
    map_path = os.path.abspath(os.path.join(ORIG_CWD, args.map))
    if args.out is not None:
        out_path = os.path.abspath(os.path.join(ORIG_CWD, args.out))
    else:
        out_path = os.path.join(EDITOR_ROOT, DEFAULT_OUT[args.tab])

    if not os.path.exists(map_path):
        sys.exit("Error: map file not found: " + map_path)

    # Fail before building the GUI so a bad --out never produces a partial file.
    fmt = os.path.splitext(out_path)[1].lstrip('.').lower()
    if fmt not in _supported_formats():
        sys.exit("Error: unsupported image format, cannot save: " + out_path)

    os.chdir(EDITOR_ROOT)
    if EDITOR_ROOT not in sys.path:
        sys.path.insert(0, EDITOR_ROOT)

    from PyQt5.QtWidgets import QApplication
    from BananaWorldEditor import TtMapEditor

    app = QApplication([])
    editor = TtMapEditor()

    with _stdout_to_stderr():
        if args.tab == 'house':
            editor.showHouseEditor()
            model = editor.model
        else:
            editor.showTerrainEditor()
            model = editor.model.map

        editor.show()
        QApplication.processEvents()

        editor.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        try:
            model.openMap(map_path)
        except Exception as e:
            sys.exit("Error: failed to load map %s: %s" % (map_path, e))

        QApplication.processEvents()

        pixmap = editor.grab()

    if not pixmap.save(out_path, None, JPEG_QUALITY):
        sys.exit("Error: failed to save screenshot to " + out_path)

    print("Saved %dx%d screenshot -> %s" % (pixmap.width(), pixmap.height(), out_path))


if __name__ == "__main__":
    main()
