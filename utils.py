"""
utils.py
--------
Contains utility functions or classes that may be shared across the application.
"""

import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette, QColor

def get_color_palette(light_palette, dark_palette):
    """
    Gets the color palette depending on the current appearance mode of the OS/QT.

    Args:
        light_palette (dict): A dictionary of color codes for light mode.
        dark_palette (dict): A dictionary of color codes for dark mode.

    Returns:
        dict: The chosen color palette based on the OS/QT background color.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    background = app.palette().color(QPalette.Window)
    darkness = (background.red() + background.green() + background.blue()) / 3
    if darkness < 128:
        return dark_palette
    return light_palette