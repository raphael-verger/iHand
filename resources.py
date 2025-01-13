"""
resources.py
------------
Stores constants, paths, and icons used throughout the application.

Attributes/Constants:
    UNIFORM_ENTRY_WIDTH (int)
    MENU_WIDTH (int)
    COLOR_PALETTE_LIGHT (dict)
    FONT_NAME (str)
    FONT_CAMERA (str)
    MODEL_PATH (str)
    LABEL_FONT (QFont)
    ENTRY_FONT (QFont)
    BUTTON_FONT (QFont)
    GEAR_ICON (QIcon)
    PAUSE_ICON (QIcon)
    PLAY_ICON (QIcon)
    DEFAULT_PRESETS (dict)
    SPECIAL_KEYS (dict)
Functions:
    init_icons()
"""

import os
import sys
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import QSize, Qt
import logging
from pynput.keyboard import Key

# Constants
UNIFORM_ENTRY_WIDTH = 210
MENU_WIDTH = 250

COLOR_PALETTE_LIGHT = {
    "MENU_BG_COLOR": "#FFFFFF",
    "LABEL_TEXT_COLOR": "#333333",
    "ENTRY_BG_COLOR": "#F0F0F0",
    "ENTRY_TEXT_COLOR": "#000000",
    "BUTTON_FG_COLOR": "#007AFF",
    "BUTTON_HOVER_COLOR": "#F0F0F0",
    "BUTTON_HOVER_COLOR_2": "#0051A8",
    "BUTTON_TEXT_COLOR": "#FFFFFF",
    "CANVAS_BG_COLOR": "#F8F8F8"
}

# Determine base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Font and model file references
FONT_NAME = "Nothing"  # Example font name
FONT_CAMERA = os.path.join(BASE_DIR, "fonts", "nothing.ttf")
MODEL_PATH = os.path.join(BASE_DIR, "models", "gesture_recognizer.task")

# Define QFont instances for uniform usage
LABEL_FONT = QFont(FONT_NAME, 14, QFont.Bold)
ENTRY_FONT = QFont(FONT_NAME, 12)
BUTTON_FONT = QFont(FONT_NAME, 14, QFont.Bold)

# Global icons (will be loaded by init_icons)
GEAR_ICON = None
PAUSE_ICON = None
PLAY_ICON = None

def init_icons():
    """
    Loads and scales icon images to QIcon objects for UI elements.
    """
    global GEAR_ICON, PAUSE_ICON, PLAY_ICON

    def load_icon(filename, size=(100, 100)):
        path = os.path.join(BASE_DIR, "icons", filename)
        pixmap = QPixmap(path)
        if pixmap.isNull():
            logging.warning(f"Could not load icon from {path}")
            return QIcon()
        pixmap = pixmap.scaled(*size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return QIcon(pixmap)

    GEAR_ICON = load_icon("settings.png", size=(100, 100))
    PAUSE_ICON = load_icon("pause.png", size=(100, 100))
    PLAY_ICON = load_icon("play.png", size=(100, 100))

DEFAULT_PRESETS = {
    "Gaming": (
        {8: 'right', 12: 'left', 16: 'm', 20: 'enter'},
        {8: 'up', 12: 'down', 16: 'command', 20: 'p'},
        "Nothing", "#FF0000"
    ),
    "Music": (
        {8: 'next', 12: 'previous', 16: 'play_pause', 20: 'cmd + L'},
        {8: 'volume_up', 12: 'volume_down', 16: 'volume_mute', 20: 'cmd + R'},
        "Brat", "#00FF00"
    ),
    "Shortcuts": (
        {8: 'cmd + space', 12: 'enter', 16: 'alt', 20: 'tab'},
        {8: 'ctrl + ctrl', 12: 'up', 16: 'down', 20: 'end'},
        "Orbitron", "#0000FF"
    ),
    "Slides": (
        {8: 'right', 12: 'left', 16: 'b', 20: 'esc'},
        {8: 'cmd + l', 12: 'cmd + p', 16: 'cmd + shift + f', 20: 'cmd + .'},
        "VT323", "#F3D25F"
    )
}

# Mapping of string key names to pynput.keyboard.Key objects
SPECIAL_KEYS = {
    'alt': Key.alt,
    'alt_gr': Key.alt_gr if hasattr(Key, 'alt_gr') else None,
    'alt_l': Key.alt_l,
    'alt_r': Key.alt_r,
    'backspace': Key.backspace,
    'caps_lock': Key.caps_lock,
    'cmd': Key.cmd,         # Mac-specific Command key
    'cmd_l': Key.cmd_l,     # Left Command key
    'cmd_r': Key.cmd_r,     # Right Command key
    'ctrl': Key.ctrl,
    'ctrl_l': Key.ctrl_l,
    'ctrl_r': Key.ctrl_r,
    'delete': Key.delete,
    'down': Key.down,
    'up': Key.up,
    'end': Key.end,
    'enter': Key.enter,
    'esc': Key.esc,
    'f1': Key.f1,
    'f2': Key.f2,
    'f3': Key.f3,
    'f4': Key.f4,
    'f5': Key.f5,
    'f6': Key.f6,
    'f7': Key.f7,
    'f8': Key.f8,
    'f9': Key.f9,
    'f10': Key.f10,
    'f11': Key.f11,
    'f12': Key.f12,
    'print_screen': Key.print_screen if hasattr(Key, 'print_screen') else None,
    'scroll_lock': Key.scroll_lock if hasattr(Key, 'scroll_lock') else None,
    'pause': Key.pause if hasattr(Key, 'pause') else None,
    'left': Key.left,
    'next': Key.media_next,
    'play_pause': Key.media_play_pause,
    'previous': Key.media_previous,
    'volume_down': Key.media_volume_down,
    'volume_mute': Key.media_volume_mute,
    'volume_up': Key.media_volume_up,
    'menu': Key.menu if hasattr(Key, 'menu') else None,
    'num_lock': Key.num_lock if hasattr(Key, 'num_lock') else None,
    'page_down': Key.page_down,
    'page_up': Key.page_up,
    'home': Key.home,
    'right': Key.right,
    'shift': Key.shift,
    'shift_l': Key.shift_l,
    'shift_r': Key.shift_r,
    'space': Key.space,
    'tab': Key.tab,
    # Add more special keys as needed
}