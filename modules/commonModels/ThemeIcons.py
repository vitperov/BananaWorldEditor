# SPDX-License-Identifier: MIT
# Copyright (c) 2022-2026 Vitaly Perov
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QStyle

# QStyle standard icons used as fallbacks when no freedesktop icon theme is
# installed (QIcon.fromTheme returns a null icon on bare systems).
NEW_FALLBACK = QStyle.SP_FileIcon
OPEN_FALLBACK = QStyle.SP_DirOpenIcon
SAVE_FALLBACK = QStyle.SP_DialogSaveButton
SAVE_AS_FALLBACK = QStyle.SP_DriveHDIcon
REFRESH_FALLBACK = QStyle.SP_BrowserReload
ADD_FALLBACK = QStyle.SP_DialogYesButton
REMOVE_FALLBACK = QStyle.SP_DialogNoButton


def themedIcon(widget, themeName, fallback=None):
    """QIcon.fromTheme with a fallback to a Qt built-in standard icon.

    Theme icons depend on a freedesktop icon theme being installed; on bare
    systems (no Adwaita/Breeze etc.) fromTheme returns an empty icon, so fall
    back to QStyle.standardIcon which is always available.
    """
    icon = QIcon.fromTheme(themeName)
    if icon.isNull() and fallback is not None:
        icon = widget.style().standardIcon(fallback)
    return icon
